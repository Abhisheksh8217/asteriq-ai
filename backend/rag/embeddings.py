"""
embeddings.py
-------------
Initializes the Google Generative AI embedding model.
Reuses the existing GOOGLE_API_KEY from .env — no new credentials needed.

Google's "models/embedding-001" is free within the Gemini API quota
and produces 768-dimensional vectors suitable for semantic search.

This module is kept separate so the embedding model can be swapped
(e.g., to HuggingFace local embeddings) without touching other modules.
"""

import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


def get_embedding_model() -> GoogleGenerativeAIEmbeddings:
    """
    Returns an initialized Google Generative AI embedding model.

    Uses 'models/embedding-001' which is optimized for semantic
    similarity tasks like document retrieval.

    Returns:
        GoogleGenerativeAIEmbeddings instance ready for use.

    Raises:
        ValueError: If GOOGLE_API_KEY is not set in environment.
    """
    if not GOOGLE_API_KEY:
        raise ValueError("[Embeddings] GOOGLE_API_KEY is not set in .env")

    embedding_model = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=GOOGLE_API_KEY,
        task_type="retrieval_document",  # Optimized for document retrieval
    )

    print("[Embeddings] Google embedding model initialized.")
    return embedding_model
