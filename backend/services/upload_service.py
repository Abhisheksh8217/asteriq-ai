"""
services/upload_service.py
--------------------------
Handles document uploads for interview sessions.
Validates file sizes and formats, writes uploads securely to session-specific folders,
saves file records to the SQLite database, and triggers RAG ingestion.
"""

import os
from typing import Dict, Any

from config import MAX_UPLOAD_SIZE_BYTES, ALLOWED_EXTENSIONS
from logger import get_logger
from services.knowledge_manager import knowledge_manager
import database
import storage

logger = get_logger(__name__)


class UploadService:
    """
    Service responsible for validating and processing uploaded candidate files (JDs, resumes, notes).
    """

    def upload_document(self, session_id: str, file_data: Any, doc_type: str = "general", email: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes an uploaded file from a Flask request.
        Validates the extension and size, saves the file to disk, logs it in the SQLite database,
        and runs document parsing/indexing.

        Args:
            session_id: Unique identifier of the current session.
            file_data: File-like object (e.g. Flask's FileStorage).
            doc_type: Type of document ('jd', 'notes', or 'general').

        Returns:
            Dict containing processing status, filenames, and ingestion statistics.

        Raises:
            ValueError: If the file type is unsupported or if the file exceeds size limits.
            IOError: If storage operations fail.
        """
        if not file_data or not file_data.filename:
            raise ValueError("No file payload provided.")

        original_filename = file_data.filename
        logger.info(
            "Received upload request: session=%s | filename=%s | type=%s",
            session_id, original_filename, doc_type
        )

        # 1. Pre-validation of file extension
        if not storage.is_allowed_file(original_filename):
            ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "unknown"
            logger.warning("Rejected upload: unsupported format '%s' for file '%s'", ext, original_filename)
            raise ValueError(
                f"File format '.{ext}' is not supported. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # 2. Ensure session directories exist before saving
        storage.create_session_dirs(session_id)

        # 3. Save file using storage layer
        save_results = storage.save_uploaded_file(
            session_id=session_id,
            file_data=file_data,
            original_filename=original_filename
        )

        stored_name = save_results["stored_name"]
        stored_path = save_results["stored_path"]
        file_size = save_results["file_size"]
        extension = save_results["extension"]

        # 4. Post-save size validation
        if file_size > MAX_UPLOAD_SIZE_BYTES:
            logger.warning(
                "Rejected upload: file size (%d bytes) exceeds maximum allowable limit (%d bytes)",
                file_size, MAX_UPLOAD_SIZE_BYTES
            )
            # Remove the over-sized file immediately to save disk space
            if os.path.exists(stored_path):
                os.unlink(stored_path)
            raise ValueError(
                f"File size exceeds the maximum limit of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB."
            )

        # 5. Persist file metadata in database
        try:
            # Check if session exists in DB. If not, create a temporary placeholder session
            # to satisfy the foreign key constraints on the uploaded_files table.
            if not database.get_session(session_id):
                database.create_session(
                    session_id=session_id,
                    mode="company",
                    topic="Pending",
                    company="Pending",
                    total_questions=5,
                    email=email
                )

            database.save_file_metadata(
                session_id=session_id,
                original_name=original_filename,
                stored_name=stored_name,
                file_type=extension,
                file_size=file_size,
                doc_type=doc_type
            )
        except Exception as e:
            logger.error("Failed to save file metadata to DB: %s. Cleaning up saved file.", e)
            if os.path.exists(stored_path):
                os.unlink(stored_path)
            raise RuntimeError(f"Database error during upload: {e}") from e

        # 6. Ingest the document into the session's vector store index
        logger.info("Triggering knowledge ingestion for session %s, file: %s", session_id, original_filename)
        try:
            ingestion_stats = knowledge_manager.ingest_document(
                session_id=session_id,
                stored_path=stored_path,
                original_filename=original_filename,
                doc_type=doc_type
            )
        except Exception as e:
            logger.error("Failed to build RAG vector index for uploaded document: %s", e)
            # We keep the file and metadata in DB, but flag the vector store error
            return {
                "success": True,
                "filename": original_filename,
                "doc_type": doc_type,
                "stored_name": stored_name,
                "ingestion_status": "failed",
                "error": f"RAG ingestion failed: {str(e)}"
            }

        return {
            "success": True,
            "filename": original_filename,
            "doc_type": doc_type,
            "stored_name": stored_name,
            "ingestion_status": "success",
            "chunks_created": ingestion_stats.get("chunk_count", 0),
            "pages_parsed": ingestion_stats.get("doc_count", 0)
        }


# Singleton instance
upload_service = UploadService()
