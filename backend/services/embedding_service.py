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
from config import GOOGLE_API_KEY, EMBEDDING_MODEL, EMBEDDING_TASK_TYPE
from logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Wraps the Google Generative AI embedding model.

    The model instance is cached after first initialization
    to avoid re-creating it on every embedding call.
    """

    def __init__(self):
        self._model = None

    def _get_model(self) -> GoogleGenerativeAIEmbeddings:
        """
        Lazily initializes and returns the embedding model.
        Cached after first call.
        """
        if self._model is None:
            if not GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY is not set in .env")

            self._model = GoogleGenerativeAIEmbeddings(
                model=EMBEDDING_MODEL,
                google_api_key=GOOGLE_API_KEY,
                task_type=EMBEDDING_TASK_TYPE,
            )
            logger.info("Embedding model initialized: %s", EMBEDDING_MODEL)

        return self._model

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
            logger.error("Query embedding failed: %s", e, exc_info=True)
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
            logger.error("Document embedding failed: %s", e, exc_info=True)
            raise RuntimeError(f"Embedding service error: {e}") from e


# Singleton instance
embedding_service = EmbeddingService()
