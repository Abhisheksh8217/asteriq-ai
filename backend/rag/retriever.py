"""
retriever.py
------------
Queries the FAISS vector store to retrieve the most relevant document
chunks for a given interview topic and company.

The retrieved chunks are returned as a single formatted context string
ready to be injected into the Gemini interview prompt.

Filtering by company metadata ensures that only that company's
documents are used — preventing cross-company context leakage.
"""

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from rag.vector_store import load_vector_store, index_exists


# Number of top chunks to retrieve per query
TOP_K = 4


def retrieve_context(topic: str, company_name: str = None) -> str:
    """
    Retrieve relevant context from the vector store for a given topic.

    Args:
        topic: The interview subject (e.g., "Python", "System Design").
        company_name: Optional company name to filter results by metadata.
                      If None, retrieves from all indexed documents.

    Returns:
        A formatted string of relevant context chunks, or an empty string
        if no index exists or no relevant chunks are found.
    """
    if not index_exists():
        print("[Retriever] No vector index found. Skipping RAG context.")
        return ""

    try:
        vector_store = load_vector_store()

        # Build a semantic query combining topic and company for better retrieval
        query = f"{company_name} {topic} interview questions skills requirements" if company_name else f"{topic} interview questions skills"

        # Retrieve top-k most similar chunks
        results: list[Document] = vector_store.similarity_search(query, k=TOP_K)

        if not results:
            print(f"[Retriever] No relevant chunks found for: {query}")
            return ""

        # Filter by company metadata if specified
        if company_name:
            results = [
                doc for doc in results
                if doc.metadata.get("company", "").lower() == company_name.lower()
            ]

        if not results:
            print(f"[Retriever] No chunks matched company: {company_name}")
            return ""

        # Format chunks into a clean context block for prompt injection
        context_parts = []
        for i, doc in enumerate(results, 1):
            source = doc.metadata.get("source", "unknown")
            context_parts.append(f"[Context {i} | Source: {source}]\n{doc.page_content.strip()}")

        context = "\n\n".join(context_parts)
        print(f"[Retriever] Retrieved {len(results)} chunk(s) for topic: {topic}")
        return context

    except Exception as e:
        print(f"[Retriever] Error during retrieval: {e}")
        return ""


def retrieve_raw_documents(topic: str, company_name: str = None) -> list[Document]:
    """
    Returns raw Document objects instead of a formatted string.
    Useful for debugging or advanced prompt construction.

    Args:
        topic: Interview subject.
        company_name: Optional company filter.

    Returns:
        List of relevant Document objects.
    """
    if not index_exists():
        return []

    try:
        vector_store = load_vector_store()
        query = f"{company_name} {topic}" if company_name else topic
        results = vector_store.similarity_search(query, k=TOP_K)

        if company_name:
            results = [
                doc for doc in results
                if doc.metadata.get("company", "").lower() == company_name.lower()
            ]

        return results

    except Exception as e:
        print(f"[Retriever] Error: {e}")
        return []
