"""
config.py
---------
Single source of truth for all application configuration.
All hardcoded values across the codebase must reference this file.
Environment variables are loaded here and never read directly in services.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# BASE PATHS
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
UPLOADS_DIR = os.path.join(STORAGE_DIR, "uploads")
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")
DEFAULT_VECTORS_DIR = os.path.join(STORAGE_DIR, "default_vectors")
DB_PATH = os.path.join(STORAGE_DIR, "interview.db")

# ─────────────────────────────────────────────
# API KEYS
# ─────────────────────────────────────────────
GOOGLE_API_KEYS_RAW = os.getenv("GOOGLE_API_KEYS", "")
# Support both the old GOOGLE_API_KEY and the new GOOGLE_API_KEYS list
if GOOGLE_API_KEYS_RAW:
    GOOGLE_API_KEYS = [k.strip() for k in GOOGLE_API_KEYS_RAW.split(",") if k.strip()]
else:
    old_key = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_API_KEYS = [old_key] if old_key else []
    
# Keep a default primary key for backwards compatibility
GOOGLE_API_KEY = GOOGLE_API_KEYS[0] if GOOGLE_API_KEYS else ""
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# SMTP EMAIL CONFIGURATION
# ─────────────────────────────────────────────
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_USER = os.getenv("SMTP_USER", SMTP_EMAIL)
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# LLM CONFIGURATION
# ─────────────────────────────────────────────
LLM_PROVIDER = "google_genai"
LLM_MODEL = "gemini-2.5-flash"
LLM_FULL_MODEL = f"{LLM_PROVIDER}:{LLM_MODEL}"

# EMBEDDING CONFIGURATION
# ─────────────────────────────────────────────
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_TASK_TYPE = "retrieval_document"

# ─────────────────────────────────────────────
# RAG / CHUNKING CONFIGURATION
# ─────────────────────────────────────────────
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K_RETRIEVAL = 4
CHUNK_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

# ─────────────────────────────────────────────
# INTERVIEW CONFIGURATION
# ─────────────────────────────────────────────
TOTAL_QUESTIONS = 5
INTERVIEWER_NAME = "ANZ"

GENERAL_TOPICS = [
    "Python",
    "Generative AI",
    "HTML",
    "CSS",
    "English",
    "Self Introduction",
]

DEFAULT_COMPANIES = ["Amazon", "Google", "Microsoft"]

# Retrieval priority weights (higher = higher priority)
PRIORITY_UPLOADED_JD = 4
PRIORITY_UPLOADED_DOCS = 3
PRIORITY_DEFAULT_COMPANY = 2
PRIORITY_GENERAL = 1

# ─────────────────────────────────────────────
# UPLOAD CONFIGURATION
# ─────────────────────────────────────────────
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}
MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# ─────────────────────────────────────────────
# EDGE-TTS CONFIGURATION
# ─────────────────────────────────────────────
EDGE_TTS_VOICE = "en-US-JennyNeural"
EDGE_TTS_RATE = "+0%"
EDGE_TTS_PITCH = "+0Hz"

# ─────────────────────────────────────────────
# GROQ WHISPER CONFIGURATION
# ─────────────────────────────────────────────
GROQ_WHISPER_MODEL = "whisper-large-v3"

# ─────────────────────────────────────────────
# SESSION CONFIGURATION
# ─────────────────────────────────────────────
SESSION_EXPIRY_HOURS = 24
MAX_CACHED_INDEXES = 20

# ─────────────────────────────────────────────
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "null"
]
if ALLOWED_ORIGINS_RAW:
    ALLOWED_ORIGINS.extend([o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()])

# ─────────────────────────────────────────────
# LOGGING CONFIGURATION
# ─────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
