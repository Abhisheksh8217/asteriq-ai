"""
services/
---------
Service layer — all business logic lives here.
Flask routes only orchestrate these services.

Modules:
    llm_service         — Gemini LLM wrapper (replaceable)
    speech_service      — Murf TTS + AssemblyAI STT (replaceable)
    embedding_service   — Google embedding model (replaceable)
    vector_store_service— Per-session FAISS index management
    knowledge_manager   — Orchestrates full RAG pipeline
    prompt_builder      — All prompt templates and construction
    interview_engine    — Core interview state and question logic
    feedback_service    — Structured feedback generation
    upload_service      — File validation, saving, and ingestion trigger
"""

from services.llm_service import llm_service
from services.speech_service import speech_service
from services.embedding_service import embedding_service
from services.vector_store_service import vector_store_service
from services.knowledge_manager import knowledge_manager
from services.prompt_builder import prompt_builder
from services.interview_engine import interview_engine
from services.feedback_service import feedback_service
from services.upload_service import upload_service

__all__ = [
    "llm_service",
    "speech_service",
    "embedding_service",
    "vector_store_service",
    "knowledge_manager",
    "prompt_builder",
    "interview_engine",
    "feedback_service",
    "upload_service",
]
