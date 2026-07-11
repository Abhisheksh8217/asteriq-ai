"""
splitter.py
-----------
Splits large documents into smaller overlapping chunks.
This is critical for RAG — embedding an entire PDF as one unit
loses semantic precision. Smaller chunks improve retrieval accuracy.

RecursiveCharacterTextSplitter is preferred because it respects
natural text boundaries (paragraphs → sentences → words) before
falling back to hard character splits.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


# Chunk size: 800 chars balances context richness vs embedding precision
# Overlap: 150 chars ensures context is not lost at chunk boundaries
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def split_documents(documents: list[Document]) -> list[Document]:
    """
    Split a list of Documents into smaller overlapping chunks.

    Args:
        documents: List of raw LangChain Document objects from loader.

    Returns:
        List of chunked Document objects with preserved metadata.
    """
    if not documents:
        print("[Splitter] No documents to split.")
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        # Split order: paragraphs → sentences → words → characters
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks = splitter.split_documents(documents)

    print(f"[Splitter] Split {len(documents)} document(s) into {len(chunks)} chunks.")
    return chunks
