"""
services/vector_store_service.py
---------------------------------
Per-session FAISS vector index management.

Each interview session gets its own isolated FAISS index built from
the documents uploaded for that session. Default company indexes are
shared and loaded once.

Responsibilities:
  - Build FAISS indexes from document chunks
  - Persist indexes to session-specific disk paths
  - Load indexes from disk with in-memory LRU-style cache
  - Merge session index with default company index for fallback retrieval
  - Check index existence without loading

Cache design:
  - Loaded indexes are cached in memory (dict keyed by session_id)
  - Cache is bounded by MAX_CACHED_INDEXES from config
  - Oldest entry is evicted when cache is full
"""

import os
from collections import OrderedDict
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from services.embedding_service import embedding_service
from storage import get_session_vectors_dir, get_default_vectors_dir
from config import MAX_CACHED_INDEXES
from logger import get_logger

logger = get_logger(__name__)

INDEX_NAME = "session_index"
DEFAULT_INDEX_NAME = "default_index"


class VectorStoreService:
    """
    Manages FAISS vector indexes per session with in-memory caching.
    """

    def __init__(self):
        # OrderedDict used as LRU cache: {session_id: FAISS instance}
        self._cache: OrderedDict = OrderedDict()

    # ─────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────

    def build_session_index(self, session_id: str, chunks: list[Document]) -> FAISS:
        """
        Builds a FAISS index from document chunks and persists it
        to the session's vectors directory.

        Args:
            session_id: The session to build the index for.
            chunks: List of chunked Document objects.

        Returns:
            The built FAISS instance (also cached in memory).

        Raises:
            ValueError: If chunks list is empty.
        """
        if not chunks:
            raise ValueError("Cannot build index — no chunks provided.")

        vectors_dir = get_session_vectors_dir(session_id)
        os.makedirs(vectors_dir, exist_ok=True)

        logger.info(
            "Building FAISS index for session %s with %d chunks...",
            session_id, len(chunks)
        )

        vector_store = FAISS.from_documents(chunks, embedding_service.model)
        vector_store.save_local(vectors_dir, index_name=INDEX_NAME)

        # Cache the newly built index
        self._cache_store(session_id, vector_store)

        logger.info("FAISS index built and saved for session: %s", session_id)
        return vector_store

    def build_default_index(self, company: str, chunks: list[Document]) -> FAISS:
        """
        Builds and persists a default company FAISS index.
        Called once when seeding default company knowledge.

        Args:
            company: Company name (amazon, google, microsoft).
            chunks: Document chunks for this company.

        Returns:
            The built FAISS instance.
        """
        if not chunks:
            raise ValueError(f"No chunks provided for default company: {company}")

        vectors_dir = get_default_vectors_dir(company)
        os.makedirs(vectors_dir, exist_ok=True)

        logger.info("Building default index for company: %s (%d chunks)", company, len(chunks))
        vector_store = FAISS.from_documents(chunks, embedding_service.model)
        vector_store.save_local(vectors_dir, index_name=DEFAULT_INDEX_NAME)

        logger.info("Default index saved for: %s", company)
        return vector_store

    # ─────────────────────────────────────────────
    # LOAD
    # ─────────────────────────────────────────────

    def load_session_index(self, session_id: str) -> FAISS:
        """
        Loads a session's FAISS index, using cache if available.

        Args:
            session_id: The session whose index to load.

        Returns:
            FAISS instance.

        Raises:
            FileNotFoundError: If no index exists for this session.
        """
        # Return from cache if available
        if session_id in self._cache:
            self._cache.move_to_end(session_id)
            logger.debug("FAISS index loaded from cache: %s", session_id)
            return self._cache[session_id]

        vectors_dir = get_session_vectors_dir(session_id)
        index_file = os.path.join(vectors_dir, f"{INDEX_NAME}.faiss")

        if not os.path.exists(index_file):
            raise FileNotFoundError(
                f"No FAISS index found for session: {session_id}"
            )

        vector_store = FAISS.load_local(
            vectors_dir,
            embedding_service.model,
            index_name=INDEX_NAME,
            allow_dangerous_deserialization=True,
        )

        self._cache_store(session_id, vector_store)
        logger.info("FAISS index loaded from disk: %s", session_id)
        return vector_store

    def load_default_index(self, company: str) -> FAISS | None:
        """
        Loads the default FAISS index for a company.
        Returns None if no default index exists yet.

        Args:
            company: Company name (case-insensitive).

        Returns:
            FAISS instance or None.
        """
        cache_key = f"default_{company.lower()}"

        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        vectors_dir = get_default_vectors_dir(company)
        index_file = os.path.join(vectors_dir, f"{DEFAULT_INDEX_NAME}.faiss")

        if not os.path.exists(index_file):
            logger.warning("No default index found for company: %s", company)
            return None

        vector_store = FAISS.load_local(
            vectors_dir,
            embedding_service.model,
            index_name=DEFAULT_INDEX_NAME,
            allow_dangerous_deserialization=True,
        )

        self._cache_store(cache_key, vector_store)
        logger.info("Default FAISS index loaded for: %s", company)
        return vector_store

    # ─────────────────────────────────────────────
    # SEARCH
    # ─────────────────────────────────────────────

    def similarity_search(self, vector_store: FAISS, query: str,
                          k: int = 4) -> list[Document]:
        """
        Performs similarity search on a FAISS index.

        Args:
            vector_store: The FAISS instance to search.
            query: The search query string.
            k: Number of top results to return.

        Returns:
            List of most relevant Document objects.
        """
        try:
            results = vector_store.similarity_search(query, k=k)
            logger.debug("Similarity search returned %d results", len(results))
            return results
        except Exception as e:
            logger.error("Similarity search failed: %s", e, exc_info=True)
            return []

    # ─────────────────────────────────────────────
    # EXISTENCE CHECKS
    # ─────────────────────────────────────────────

    def session_index_exists(self, session_id: str) -> bool:
        """Returns True if a FAISS index exists for this session."""
        vectors_dir = get_session_vectors_dir(session_id)
        return os.path.exists(os.path.join(vectors_dir, f"{INDEX_NAME}.faiss"))

    def default_index_exists(self, company: str) -> bool:
        """Returns True if a default FAISS index exists for this company."""
        vectors_dir = get_default_vectors_dir(company)
        return os.path.exists(os.path.join(vectors_dir, f"{DEFAULT_INDEX_NAME}.faiss"))

    def evict_session(self, session_id: str) -> None:
        """Removes a session's index from the in-memory cache."""
        if session_id in self._cache:
            del self._cache[session_id]
            logger.info("Evicted session index from cache: %s", session_id)

    # ─────────────────────────────────────────────
    # INTERNAL
    # ─────────────────────────────────────────────

    def _cache_store(self, key: str, store: FAISS) -> None:
        """
        Adds a FAISS store to the cache, evicting the oldest entry
        if the cache exceeds MAX_CACHED_INDEXES.
        """
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= MAX_CACHED_INDEXES:
                evicted_key, _ = self._cache.popitem(last=False)
                logger.info("Cache full — evicted oldest index: %s", evicted_key)
            self._cache[key] = store


# Singleton instance
vector_store_service = VectorStoreService()
