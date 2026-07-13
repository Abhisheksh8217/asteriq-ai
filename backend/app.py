"""
app.py
------
Thin Flask controller routing HTTP endpoints to the modular service layer.
No business logic, direct LLM execution, or transcription calls are handled here.

Initializes folders, databases, and company RAG stores on startup.
"""

import uuid
from flask import Flask, request, jsonify, Response, make_response

from config import ALLOWED_ORIGINS
from logger import get_logger
from services import interview_engine, feedback_service, upload_service
from services.auth_service import auth_service, token_required
import database
import storage

logger = get_logger(__name__)

app = Flask(__name__)


def cors_headers(response: Response) -> Response:
    """
    Applies CORS compliance headers based on allowed config origins.
    Exposes custom session and state headers to the client.
    """
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = ALLOWED_ORIGINS[0]
        
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Expose-Headers'] = 'X-Question-Number, X-Interview-Complete, X-Session-ID'
    return response


@app.before_request
def before_request():
    logger.info("Incoming request: %s %s from Origin: %s", request.method, request.path, request.headers.get("Origin"))


@app.after_request
def after_request(response: Response) -> Response:
    return cors_headers(response)


@app.errorhandler(Exception)
def handle_exception(e: Exception):
    logger.error("Unhandled exception in route handler: %s", e, exc_info=True)
    response = jsonify({"success": False, "error": str(e)})
    response.status_code = 500
    return cors_headers(response)


@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    return cors_headers(app.make_default_options_response())


# ─────────────────────────────────────────────
# AUTHENTICATION ROUTES
# ─────────────────────────────────────────────

@app.route("/register", methods=["POST"])
def register():
    """
    Registers a new user profile.
    Expects JSON: { "email": "...", "password": "..." }
    """
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")

    success, msg = auth_service.register(email, password, name=name)
    if success:
        return jsonify({"success": True, "message": msg}), 201
    else:
        return jsonify({"success": False, "error": msg}), 400


@app.route("/login", methods=["POST"])
def login():
    """
    Logs in an existing user and returns a session auth token.
    Expects JSON: { "email": "...", "password": "..." }
    """
    data = request.json or {}
    email = data.get("email")
    password = data.get("password")

    token, msg = auth_service.login(email, password)
    if token:
        return jsonify({"success": True, "token": token, "email": email.lower(), "message": msg}), 200
    else:
        return jsonify({"success": False, "error": msg}), 401


@app.route("/logout", methods=["POST"])
def logout():
    """
    Logs out the user and revokes their session token.
    """
    token = None
    if "Authorization" in request.headers:
        auth_header = request.headers["Authorization"]
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if token:
        auth_service.logout(token)
    return jsonify({"success": True, "message": "Logged out successfully."})


@app.route("/validate-token", methods=["GET"])
@token_required
def validate_token(current_user):
    """
    Confirms an auth token is still active and valid.
    """
    return jsonify({"success": True, "email": current_user})


@app.route("/get-sessions", methods=["GET"])
@token_required
def get_sessions(current_user):
    """
    Retrieves all past interview sessions for the logged-in user.
    """
    sessions = database.get_user_sessions(current_user)
    return jsonify({"success": True, "sessions": sessions})


@app.route("/get-session-state/<session_id>", methods=["GET"])
@token_required
def get_session_state(current_user, session_id):
    """
    Retrieves the complete state of a session to restore frontend UI on page load/refresh.
    """
    session = database.get_session(session_id)
    if not session:
        return jsonify({"success": False, "error": "Session not found."}), 404

    # Security check: ensure session belongs to authenticated user
    if session.get("email") != current_user:
        return jsonify({"success": False, "error": "Access denied."}), 403

    history = database.get_interview_history(session_id)
    files = database.get_session_files(session_id)

    return jsonify({
        "success": True,
        "session": session,
        "history": history,
        "files": files
    })


# ─────────────────────────────────────────────
# CORE ROUTES
# ─────────────────────────────────────────────

@app.route("/start-interview", methods=["POST"])
@token_required
def start_interview(current_user):
    """
    Starts an interview session.
    Expects JSON: { "session_id": "...", "mode": "...", "subject": "...", "company": "..." }
    """
    data = request.json or {}
    session_id = data.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info("Generated new session ID for start-interview: %s", session_id)

    mode = data.get("mode", "general")
    subject = data.get("subject", "Python")
    company = data.get("company")

    total_questions = 10 if mode == "company" else 5

    # Start session execution flow
    question_text, audio_base64 = interview_engine.start_interview(
        session_id=session_id,
        mode=mode,
        topic=subject,
        company=company,
        email=current_user,
        total_questions=total_questions
    )

    response = make_response(jsonify({
        "success": True,
        "session_id": session_id,
        "question": question_text,
        "audio": audio_base64
    }))
    response.headers['X-Session-ID'] = session_id
    return response


@app.route("/submit-answer", methods=["POST"])
@token_required
def submit_answer(current_user):
    """
    Processes candidate answer file upload.
    Reads session_id dynamically from URL queries or form-data body.
    """
    session_id = request.args.get("session_id") or request.form.get("session_id")
    if not session_id:
        return jsonify({"success": False, "error": "Missing 'session_id' parameter."}), 400

    # Security check: ensure session belongs to current user
    session = database.get_session(session_id)
    if session and session.get("email") != current_user:
        return jsonify({"success": False, "error": "Access denied. Session belongs to another profile."}), 403

    if "audio" not in request.files:
        return jsonify({"success": False, "error": "Missing 'audio' file payload."}), 400

    audio_file = request.files["audio"]

    # Submit answer and retrieve audio reply
    question_text, audio_base64, headers = interview_engine.submit_answer(session_id, audio_file)

    response = make_response(jsonify({
        "success": True,
        "question": question_text,
        "audio": audio_base64
    }))
    for k, v in headers.items():
        response.headers[k] = v
    return response


@app.route("/upload-document", methods=["POST"])
@token_required
def upload_document(current_user):
    """
    Handles PDF/TXT document uploads for the session.
    Ingests and creates vector indices in background.
    """
    session_id = request.args.get("session_id") or request.form.get("session_id")
    if not session_id:
        return jsonify({"success": False, "error": "Missing 'session_id' parameter."}), 400

    if "file" not in request.files:
        return jsonify({"success": False, "error": "Missing 'file' payload."}), 400

    file_data = request.files["file"]
    doc_type = request.form.get("doc_type", "general")

    # Process and build FAISS index
    result = upload_service.upload_document(session_id, file_data, doc_type, email=current_user)
    return jsonify(result)


@app.route("/get-feedback", methods=["POST"])
@token_required
def get_feedback(current_user):
    """
    Compiles detailed session evaluation grades.
    """
    data = request.json or {}
    session_id = data.get("session_id") or request.args.get("session_id")
    if not session_id:
        return jsonify({"success": False, "error": "Missing 'session_id' parameter."}), 400

    # Security check: ensure session belongs to current user
    session = database.get_session(session_id)
    if session and session.get("email") != current_user:
        return jsonify({"success": False, "error": "Access denied."}), 403

    # Generate and compile feedback metrics
    feedback_data = feedback_service.generate_feedback(session_id)
    return jsonify({"success": True, "feedback": feedback_data})


# ─────────────────────────────────────────────
# BOOTSTRAPPING
# ─────────────────────────────────────────────

def bootstrap_company_indexes():
    """
    Scans company_docs/ directory and builds FAISS indexes for Google, Amazon,
    and Microsoft if they are missing in vector_store_service.
    """
    from services.vector_store_service import vector_store_service
    from services.knowledge_manager import knowledge_manager
    import os

    companies = ["Google", "Amazon", "Microsoft"]
    for company in companies:
        if not vector_store_service.default_index_exists(company):
            logger.info("Default vector store index for %s not found. Bootstrapping profile...", company)
            company_dir = os.path.join("company_docs", company)
            if not os.path.exists(company_dir):
                logger.warning("Company directory %s does not exist. Skipping...", company_dir)
                continue

            raw_docs = []
            for filename in os.listdir(company_dir):
                filepath = os.path.join(company_dir, filename)
                if os.path.isfile(filepath):
                    try:
                        docs = knowledge_manager._parse_file(filepath)
                        raw_docs.extend(docs)
                    except Exception as e:
                        logger.error("Failed to parse bootstrap document %s: %s", filepath, e)

            if raw_docs:
                try:
                    chunks = knowledge_manager._split_text(raw_docs)
                    # Force company tagging for default index items
                    for doc in chunks:
                        doc.metadata["doc_type"] = "company"
                        doc.metadata["company"] = company

                    vector_store_service.build_default_index(company, chunks)
                    logger.info("Successfully bootstrapped default index for %s with %d chunks.", company, len(chunks))
                except Exception as e:
                    logger.error("Failed to build default index for %s: %s", company, e)
            else:
                logger.warning("No readable documents found for bootstrapping company: %s", company)
        else:
            logger.info("Default vector store index for %s already exists.", company)


# ─────────────────────────────────────────────
# SERVER RUN & INITIALIZATION
# ─────────────────────────────────────────────

def init_app():
    logger.info("Initializing system infrastructure and layers...")
    database.init_db()
    storage.init_storage()

    # Run automatic session storage cleanup
    cleaned_sessions = storage.cleanup_expired_sessions()
    if cleaned_sessions:
        logger.info("Cleaned up %d expired session directories on launch.", cleaned_sessions)

    # Ingest default company profiles
    bootstrap_company_indexes()

# Run initialization immediately when imported by Gunicorn
init_app()


if __name__ == "__main__":
    logger.info("Starting Flask application server on port 5000...")
    app.run(debug=True, port=5000, use_reloader=False)
