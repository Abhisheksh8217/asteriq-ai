"""
database.py
-----------
SQLite database layer for the application.

Stores:
  - interview_sessions  : session metadata, mode, company, topic, status
  - interview_history   : per-question records (question, answer, score)
  - uploaded_files      : file metadata per session
  - session_vectors     : FAISS index paths per session

Embeddings are NEVER stored here — only paths to FAISS index files on disk.

All functions use context managers to ensure connections are always closed.
Thread safety is handled via check_same_thread=False + WAL journal mode.
"""

import psycopg2
import psycopg2.extras
import os
from datetime import datetime, timedelta
from typing import Optional
from config import DATABASE_URL, STORAGE_DIR
from logger import get_logger

logger = get_logger(__name__)

# Ensure storage directory exists before DB is created
os.makedirs(STORAGE_DIR, exist_ok=True)


def get_connection():
    """
    Returns a PostgreSQL connection.
    """
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _execute(conn, query, params=None):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if params:
        cur.execute(query, params)
    else:
        cur.execute(query)
    return cur

def init_db() -> None:
    """
    Creates all tables if they do not exist.
    Safe to call on every application startup.
    Runs self-healing schema migration if transitioning from username to email layouts.
    """
    with get_connection() as conn:
        # Self-healing Migration Check: Check if old users table has username column
        table_check = _execute(conn, 
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='users'"
        ).fetchone()
        
        if table_check:
            # Table users exists. Check if it has 'email' column
            try:
                _execute(conn, "SELECT email FROM users LIMIT 1")
            except psycopg2.OperationalError:
                # OperationalError: no such column: email (meaning it has username column)
                logger.warning("Old username database schema detected. Performing self-healing drop to recreate with email layout...")
                _execute(conn, "DROP TABLE IF EXISTS user_tokens")
                _execute(conn, "DROP TABLE IF EXISTS interview_history")
                _execute(conn, "DROP TABLE IF EXISTS uploaded_files")
                _execute(conn, "DROP TABLE IF EXISTS session_vectors")
                _execute(conn, "DROP TABLE IF EXISTS interview_sessions")
                _execute(conn, "DROP TABLE IF EXISTS users")
                logger.info("Dropped old tables successfully.")

        _execute(conn, """
            CREATE TABLE IF NOT EXISTS users (
                email           TEXT PRIMARY KEY,
                password_hash   TEXT NOT NULL,
                name            TEXT,
                created_at      TEXT NOT NULL
            )
        """)

        _execute(conn, """
            CREATE TABLE IF NOT EXISTS user_tokens (
                token           TEXT PRIMARY KEY,
                email           TEXT NOT NULL,
                expires_at      TEXT NOT NULL,
                FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE
            )
        """)

        _execute(conn, """
            CREATE TABLE IF NOT EXISTS interview_sessions (
                session_id      TEXT PRIMARY KEY,
                mode            TEXT NOT NULL CHECK(mode IN ('general', 'company')),
                topic           TEXT,
                company         TEXT,
                status          TEXT NOT NULL DEFAULT 'active'
                                    CHECK(status IN ('active', 'completed', 'abandoned')),
                question_count  INTEGER NOT NULL DEFAULT 0,
                total_questions INTEGER NOT NULL DEFAULT 5,
                email           TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                completed_at    TEXT,
                FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE
            )
        """)

        _execute(conn, """
            CREATE TABLE IF NOT EXISTS interview_history (
                id              SERIAL PRIMARY KEY,
                session_id      TEXT NOT NULL,
                question_number INTEGER NOT NULL,
                question        TEXT NOT NULL,
                answer          TEXT,
                asked_at        TEXT NOT NULL,
                answered_at     TEXT,
                FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
                    ON DELETE CASCADE
            )
        """)

        _execute(conn, """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id              SERIAL PRIMARY KEY,
                session_id      TEXT NOT NULL,
                original_name   TEXT NOT NULL,
                stored_name     TEXT NOT NULL,
                file_type       TEXT NOT NULL,
                file_size       INTEGER NOT NULL,
                doc_type        TEXT NOT NULL DEFAULT 'general'
                                    CHECK(doc_type IN ('jd', 'notes', 'general')),
                uploaded_at     TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
                    ON DELETE CASCADE
            )
        """)

        _execute(conn, """
            CREATE TABLE IF NOT EXISTS session_vectors (
                session_id      TEXT PRIMARY KEY,
                vector_path     TEXT NOT NULL,
                doc_count       INTEGER NOT NULL DEFAULT 0,
                chunk_count     INTEGER NOT NULL DEFAULT 0,
                built_at        TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
                    ON DELETE CASCADE
            )
        """)

        # Ensure topic column is nullable for Company RAG mode (dynamic schema self-healing)
        try:
            _execute(conn, "ALTER TABLE interview_sessions ALTER COLUMN topic DROP NOT NULL")
        except Exception as e:
            logger.debug("Failed to alter topic column nullability (safe if SQLite or already nullable): %s", e)

        # Old migrations removed to prevent Postgres transaction aborts.

    logger.info("Database initialized with PostgreSQL connection.")


# ─────────────────────────────────────────────
# SESSION OPERATIONS
# ─────────────────────────────────────────────

def create_session(session_id: str, mode: str, topic: str,
                   company: Optional[str] = None,
                   total_questions: int = 5,
                   email: Optional[str] = None) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        # Check if session already exists (e.g. created as a placeholder during document upload)
        row = _execute(conn, 
            "SELECT 1 FROM interview_sessions WHERE session_id = %s", (session_id,)
        ).fetchone()
        if row:
            # Update the existing placeholder session dynamically
            _execute(conn, """
                UPDATE interview_sessions
                SET mode = %s, topic = %s, company = %s, total_questions = %s, email = %s, updated_at = %s
                WHERE session_id = %s
            """, (mode, topic, company, total_questions, email, now, session_id))
            logger.info("Session updated: %s | mode=%s | topic=%s | company=%s | email=%s", session_id, mode, topic, company, email)
        else:
            # Insert a new session record
            _execute(conn, """
                INSERT INTO interview_sessions
                    (session_id, mode, topic, company, status,
                     question_count, total_questions, email, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'active', 0, %s, %s, %s, %s)
            """, (session_id, mode, topic, company, total_questions, email, now, now))
            logger.info("Session created: %s | mode=%s | topic=%s | email=%s", session_id, mode, topic, email)


def get_session(session_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = _execute(conn, 
            "SELECT * FROM interview_sessions WHERE session_id = %s", (session_id,)
        ).fetchone()
    return dict(row) if row else None


def update_session_question_count(session_id: str, count: int) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        _execute(conn, """
            UPDATE interview_sessions
            SET question_count = %s, updated_at = %s
            WHERE session_id = %s
        """, (count, now, session_id))


def complete_session(session_id: str) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        _execute(conn, """
            UPDATE interview_sessions
            SET status = 'completed', completed_at = %s, updated_at = %s
            WHERE session_id = %s
        """, (now, now, session_id))
    logger.info("Session completed: %s", session_id)


def delete_session(session_id: str) -> None:
    with get_connection() as conn:
        _execute(conn, 
            "DELETE FROM interview_sessions WHERE session_id = %s", (session_id,)
        )
    logger.info("Session deleted: %s", session_id)


# ─────────────────────────────────────────────
# INTERVIEW HISTORY OPERATIONS
# ─────────────────────────────────────────────

def save_question(session_id: str, question_number: int, question: str) -> int:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = _execute(conn, """
            INSERT INTO interview_history (session_id, question_number, question, asked_at)
            VALUES (%s, %s, %s, %s)
        """, (session_id, question_number, question, now))
    return cursor.lastrowid


def save_answer(session_id: str, question_number: int, answer: str) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        _execute(conn, """
            UPDATE interview_history
            SET answer = %s, answered_at = %s
            WHERE session_id = %s AND question_number = %s
        """, (answer, now, session_id, question_number))


def get_interview_history(session_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = _execute(conn, """
            SELECT * FROM interview_history
            WHERE session_id = %s
            ORDER BY question_number ASC
        """, (session_id,)).fetchall()
    return [dict(row) for row in rows]


# ─────────────────────────────────────────────
# UPLOADED FILES OPERATIONS
# ─────────────────────────────────────────────

def save_file_metadata(session_id: str, original_name: str, stored_name: str,
                       file_type: str, file_size: int, doc_type: str = "general") -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        _execute(conn, """
            INSERT INTO uploaded_files
                (session_id, original_name, stored_name, file_type,
                 file_size, doc_type, uploaded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (session_id, original_name, stored_name, file_type,
              file_size, doc_type, now))
    logger.info("File metadata saved: %s -> %s", original_name, stored_name)


def get_session_files(session_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = _execute(conn, 
            "SELECT * FROM uploaded_files WHERE session_id = %s ORDER BY uploaded_at",
            (session_id,)
        ).fetchall()
    return [dict(row) for row in rows]


# ─────────────────────────────────────────────
# VECTOR STORE OPERATIONS
# ─────────────────────────────────────────────

def save_vector_path(session_id: str, vector_path: str,
                     doc_count: int, chunk_count: int) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        _execute(conn, """
            INSERT INTO session_vectors
                (session_id, vector_path, doc_count, chunk_count, built_at)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT (session_id) DO UPDATE SET vector_path=EXCLUDED.vector_path, doc_count=EXCLUDED.doc_count, chunk_count=EXCLUDED.chunk_count, built_at=EXCLUDED.built_at
        """, (session_id, vector_path, doc_count, chunk_count, now))
    logger.info("Vector path saved for session: %s -> %s", session_id, vector_path)


def get_vector_path(session_id: str) -> Optional[str]:
    with get_connection() as conn:
        row = _execute(conn, 
            "SELECT vector_path FROM session_vectors WHERE session_id = %s",
            (session_id,)
        ).fetchone()
    return row["vector_path"] if row else None


# ─────────────────────────────────────────────
# USER OPERATIONS
# ─────────────────────────────────────────────

def create_user(email: str, password_hash: str, name: Optional[str] = None) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        _execute(conn, """
            INSERT INTO users (email, password_hash, name, created_at)
            VALUES (%s, %s, %s, %s)
        """, (email, password_hash, name, now))
    logger.info("User registered: %s | name=%s", email, name)


def get_user(email: str) -> Optional[dict]:
    with get_connection() as conn:
        row = _execute(conn, 
            "SELECT * FROM users WHERE email = %s", (email,)
        ).fetchone()
    return dict(row) if row else None


def get_user_sessions(email: str) -> list[dict]:
    with get_connection() as conn:
        rows = _execute(conn, """
            SELECT * FROM interview_sessions 
            WHERE email = %s
            ORDER BY created_at DESC
        """, (email,)).fetchall()
    return [dict(row) for row in rows]


# ─────────────────────────────────────────────
# TOKEN OPERATIONS
# ─────────────────────────────────────────────

def create_token(email: str, lifespan_days: int = 7) -> str:
    import uuid
    token = uuid.uuid4().hex
    expiry = (datetime.utcnow() + timedelta(days=lifespan_days)).isoformat()
    with get_connection() as conn:
        _execute(conn, """
            INSERT INTO user_tokens (token, email, expires_at)
            VALUES (%s, %s, %s)
        """, (token, email, expiry))
    return token


def get_email_by_token(token: str) -> Optional[str]:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        # Delete expired tokens first to keep the table clean
        _execute(conn, "DELETE FROM user_tokens WHERE expires_at < %s", (now,))
        
        row = _execute(conn, """
            SELECT email FROM user_tokens
            WHERE token = %s AND expires_at >= %s
        """, (token, now)).fetchone()
    return row["email"] if row else None


def delete_token(token: str) -> None:
    with get_connection() as conn:
        _execute(conn, "DELETE FROM user_tokens WHERE token = %s", (token,))
    logger.info("Token invalidated: %s", token[:6] + "...")
