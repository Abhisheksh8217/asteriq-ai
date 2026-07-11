"""
vector_store.py
---------------
Manages the FAISS vector store — creation, persistence, and loading.

FAISS (Facebook AI Similarity Search) is chosen because:
- Fully local, no external service or API cost
- Fast similarity search even with thousands of chunks
- LangChain has native FAISS integration
- Index persists to disk so re-embedding is not needed on every restart

The index is saved to the vector_store/ directory at the project root.
"""

import os
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from rag.embeddings import get_embedding_model


# Path to persist the FAISS index on disk
VECTOR_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "vector_store")
INDEX_NAME = "company_index"


def build_vector_store(chunks: list[Document]) -> FAISS:
    """
    Build a new FAISS vector store from document chunks and persist it.

    Args:
        chunks: List of chunked Document objects from splitter.

    Returns:
        FAISS vector store instance.

    Raises:
        ValueError: If chunks list is empty.
    """
    if not chunks:
        raise ValueError("[VectorStore] Cannot build index — no chunks provided.")

    print(f"[VectorStore] Building FAISS index from {len(chunks)} chunks...")

    embedding_model = get_embedding_model()
    vector_store = FAISS.from_documents(chunks, embedding_model)

    # Persist index to disk
    os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
    vector_store.save_local(VECTOR_STORE_DIR, index_name=INDEX_NAME)

    print(f"[VectorStore] Index saved to: {VECTOR_STORE_DIR}")
    return vector_store


def load_vector_store() -> FAISS:
    """
    Load an existing FAISS index from disk.

    Returns:
        FAISS vector store instance loaded from disk.

    Raises:
        FileNotFoundError: If no persisted index exists yet.
    """
    index_path = os.path.join(VECTOR_STORE_DIR, f"{INDEX_NAME}.faiss")

    if not os.path.exists(index_path):
        raise FileNotFoundError(
            f"[VectorStore] No index found at {index_path}. "
            "Run index_builder.py first to build the index."
        )

    embedding_model = get_embedding_model()
    vector_store = FAISS.load_local(
        VECTOR_STORE_DIR,
        embedding_model,
        index_name=INDEX_NAME,
        allow_dangerous_deserialization=True,  # Required by LangChain for local FAISS
    )

    print(f"[VectorStore] Index loaded from: {VECTOR_STORE_DIR}")
    return vector_store


def index_exists() -> bool:
    """
    Check whether a persisted FAISS index exists on disk.

    Returns:
        True if index files are present, False otherwise.
    """
    index_path = os.path.join(VECTOR_STORE_DIR, f"{INDEX_NAME}.faiss")
    return os.path.exists(index_path)
