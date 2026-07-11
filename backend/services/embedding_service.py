"""
services/embedding_service.py
------------------------------
Google Generative AI embedding model wrapper.

Designed as a replaceable abstraction — swapping to HuggingFace,
OpenAI, or local embeddings only requires changing this file.

Uses lazy initialization so the model is only loaded when first needed,
not at import time. This prevents startup failures if the API key
is temporarily unavailable.
"""

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config import GOOGLE_API_KEYS, EMBEDDING_MODEL, EMBEDDING_TASK_TYPE
from logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Wraps the Google Generative AI embedding model.

    Supports multi-key fallback rotation and instant fail-fast behavior
    to prevent Gunicorn timeouts during rate limits.
    """

    def __init__(self):
        self._model = None
        self._current_api_key = GOOGLE_API_KEYS[0] if GOOGLE_API_KEYS else ""

    def _initialize_model(self, api_key: str) -> None:
        """Initializes the embedding model with the specified API key."""
        if not api_key:
            raise ValueError("No Google API Key available for embedding model")
        self._model = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=api_key,
            task_type=EMBEDDING_TASK_TYPE,
            max_retries=0
        )
        self._current_api_key = api_key

    def _get_model(self) -> GoogleGenerativeAIEmbeddings:
        """
        Lazily initializes and returns the embedding model.
        Cached after first call.
        """
        if self._model is None:
            self._initialize_model(self._current_api_key)
            logger.info("Embedding model initialized: %s", EMBEDDING_MODEL)
        return self._model

    def _rotate_key_and_retry(self) -> bool:
        """Rotates the current API key to a fallback key if available."""
        global GOOGLE_API_KEYS
        if len(GOOGLE_API_KEYS) <= 1:
            return False
            
        failed_key = self._current_api_key
        if failed_key in GOOGLE_API_KEYS:
            GOOGLE_API_KEYS.remove(failed_key)
            GOOGLE_API_KEYS.append(failed_key)
            
        new_key = GOOGLE_API_KEYS[0]
        logger.info("Rotating embedding API key to fallback key...")
        try:
            self._initialize_model(new_key)
            return True
        except Exception as e:
            logger.error("Failed to initialize embedding model with fallback key: %s", e)
            return False

    @property
    def model(self) -> GoogleGenerativeAIEmbeddings:
        """
        Public property to access the embedding model.
        Used by vector_store_service when building FAISS indexes.
        """
        return self._get_model()

    def embed_query(self, text: str) -> list[float]:
        """
        Embeds a single query string for similarity search.

        Args:
            text: Query text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        try:
            return self._get_model().embed_query(text)
        except Exception as e:
            logger.warning("Query embedding failed: %s. Attempting fallback...", e)
            if self._rotate_key_and_retry():
                try:
                    return self._get_model().embed_query(text)
                except Exception as retry_err:
                    logger.error("Query embedding fallback failed: %s", retry_err, exc_info=True)
                    raise
            raise RuntimeError(f"Embedding service error: {e}") from e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embeds a list of document strings in batch.

        Args:
            texts: List of document strings to embed.

        Returns:
            List of embedding vectors.
        """
        try:
            return self._get_model().embed_documents(texts)
        except Exception as e:
            logger.warning("Document embedding failed: %s. Attempting fallback...", e)
            if self._rotate_key_and_retry():
                try:
                    return self._get_model().embed_documents(texts)
                except Exception as retry_err:
                    logger.error("Document embedding fallback failed: %s", retry_err, exc_info=True)
                    raise
            raise RuntimeError(f"Embedding service error: {e}") from e


# Singleton instance
embedding_service = EmbeddingService()
