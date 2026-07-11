"""
storage.py
----------
Manages all filesystem operations for the application.

Responsibilities:
  - Create per-session directory structure
  - Generate safe unique filenames for uploads
  - Resolve paths for documents and vector indexes
  - Clean up expired session directories

Directory structure per session:
    storage/
    └── uploads/
        └── {session_id}/
            ├── documents/     ← uploaded PDFs, TXTs, DOCXs
            └── vectors/       ← FAISS index files for this session

Default company vectors are stored separately:
    storage/
    └── default_vectors/
        ├── amazon/
        ├── google/
        └── microsoft/
"""

import os
import uuid
import shutil
from datetime import datetime, timedelta
from config import (
    UPLOADS_DIR, DEFAULT_VECTORS_DIR, STORAGE_DIR,
    ALLOWED_EXTENSIONS, SESSION_EXPIRY_HOURS
)
from logger import get_logger

logger = get_logger(__name__)


def init_storage() -> None:
    """
    Creates all required top-level storage directories on startup.
    Safe to call multiple times.
    """
    dirs = [
        STORAGE_DIR,
        UPLOADS_DIR,
        DEFAULT_VECTORS_DIR,
        os.path.join(DEFAULT_VECTORS_DIR, "amazon"),
        os.path.join(DEFAULT_VECTORS_DIR, "google"),
        os.path.join(DEFAULT_VECTORS_DIR, "microsoft"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    logger.info("Storage directories initialized at: %s", STORAGE_DIR)


def create_session_dirs(session_id: str) -> dict:
    """
    Creates the documents/ and vectors/ subdirectories for a session.

    Args:
        session_id: Unique session identifier.

    Returns:
        Dict with keys 'documents' and 'vectors' pointing to absolute paths.
    """
    docs_dir = os.path.join(UPLOADS_DIR, session_id, "documents")
    vectors_dir = os.path.join(UPLOADS_DIR, session_id, "vectors")

    os.makedirs(docs_dir, exist_ok=True)
    os.makedirs(vectors_dir, exist_ok=True)

    logger.info("Session directories created for: %s", session_id)
    return {"documents": docs_dir, "vectors": vectors_dir}


def get_session_docs_dir(session_id: str) -> str:
    """Returns the absolute path to the session's documents directory."""
    return os.path.join(UPLOADS_DIR, session_id, "documents")


def get_session_vectors_dir(session_id: str) -> str:
    """Returns the absolute path to the session's FAISS vectors directory."""
    return os.path.join(UPLOADS_DIR, session_id, "vectors")


def get_default_vectors_dir(company: str) -> str:
    """Returns the absolute path to a default company's vectors directory."""
    return os.path.join(DEFAULT_VECTORS_DIR, company.lower())


def generate_safe_filename(original_filename: str) -> str:
    """
    Generates a UUID-based filename to prevent path traversal attacks
    and filename collisions. Preserves the original file extension.

    Args:
        original_filename: The filename as provided by the user.

    Returns:
        A safe unique filename like '3f2a1b4c-...-uuid.pdf'
    """
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
    return f"{uuid.uuid4().hex}.{ext}"


def is_allowed_file(filename: str) -> bool:
    """
    Validates that the file extension is in the allowed list.

    Args:
        filename: Original filename from the upload.

    Returns:
        True if extension is allowed, False otherwise.
    """
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_EXTENSIONS


def save_uploaded_file(session_id: str, file_data, original_filename: str) -> dict:
    """
    Saves an uploaded file to the session's documents directory.

    Args:
        session_id: The current session ID.
        file_data: File-like object (e.g., from Flask request.files).
        original_filename: Original name of the uploaded file.

    Returns:
        Dict with stored_name, stored_path, file_size, extension.

    Raises:
        ValueError: If file type is not allowed.
        IOError: If file cannot be saved.
    """
    if not is_allowed_file(original_filename):
        raise ValueError(
            f"File type not allowed: '{original_filename}'. "
            f"Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    docs_dir = get_session_docs_dir(session_id)
    os.makedirs(docs_dir, exist_ok=True)

    stored_name = generate_safe_filename(original_filename)
    stored_path = os.path.join(docs_dir, stored_name)

    file_data.save(stored_path)
    file_size = os.path.getsize(stored_path)

    logger.info(
        "File saved: '%s' -> '%s' (%d bytes) for session %s",
        original_filename, stored_name, file_size, session_id
    )

    return {
        "stored_name": stored_name,
        "stored_path": stored_path,
        "file_size": file_size,
        "extension": original_filename.rsplit(".", 1)[-1].lower(),
    }


def delete_session_storage(session_id: str) -> None:
    """
    Deletes all files and directories for a session.
    Called when a session is explicitly deleted or expires.

    Args:
        session_id: The session to clean up.
    """
    session_dir = os.path.join(UPLOADS_DIR, session_id)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
        logger.info("Session storage deleted: %s", session_id)
    else:
        logger.warning("Session storage not found for deletion: %s", session_id)


def cleanup_expired_sessions() -> int:
    """
    Scans the uploads directory and removes session folders older than
    SESSION_EXPIRY_HOURS. Should be called periodically.

    Returns:
        Number of session directories cleaned up.
    """
    if not os.path.exists(UPLOADS_DIR):
        return 0

    cutoff = datetime.utcnow() - timedelta(hours=SESSION_EXPIRY_HOURS)
    cleaned = 0

    for session_id in os.listdir(UPLOADS_DIR):
        session_dir = os.path.join(UPLOADS_DIR, session_id)
        if not os.path.isdir(session_dir):
            continue

        mtime = datetime.utcfromtimestamp(os.path.getmtime(session_dir))
        if mtime < cutoff:
            shutil.rmtree(session_dir)
            cleaned += 1
            logger.info("Expired session storage removed: %s", session_id)

    if cleaned:
        logger.info("Cleanup complete. Removed %d expired session(s).", cleaned)
    return cleaned


def session_storage_exists(session_id: str) -> bool:
    """Returns True if the session's storage directory exists."""
    return os.path.isdir(os.path.join(UPLOADS_DIR, session_id))


def list_session_files(session_id: str) -> list[str]:
    """
    Lists all filenames in the session's documents directory.

    Returns:
        List of stored filenames (not full paths).
    """
    docs_dir = get_session_docs_dir(session_id)
    if not os.path.exists(docs_dir):
        return []
    return [f for f in os.listdir(docs_dir) if os.path.isfile(os.path.join(docs_dir, f))]
