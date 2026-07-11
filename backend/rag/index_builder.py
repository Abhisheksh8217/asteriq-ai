"""
index_builder.py
----------------
Entry point for building or rebuilding the FAISS vector index.

Run this script manually whenever new company documents are added
to the company_docs/ directory:

    python rag/index_builder.py
    python rag/index_builder.py --company Google
    python rag/index_builder.py --rebuild

This script orchestrates the full RAG pipeline:
    loader → splitter → embeddings → vector_store
"""

import sys
import os
import argparse

# Ensure backend root is on the path when running this file directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rag.loader import load_documents
from rag.splitter import split_documents
from rag.vector_store import build_vector_store, load_vector_store, index_exists
from langchain_community.vectorstores import FAISS


def build_index(company_name: str = None, rebuild: bool = False) -> bool:
    """
    Full pipeline: load → split → embed → store.

    Args:
        company_name: Optional — index only this company's documents.
        rebuild: If True, rebuilds the entire index from scratch.
                 If False and index exists, merges new docs into existing index.

    Returns:
        True if index was built successfully, False otherwise.
    """
    print("\n" + "=" * 50)
    print("RAG Index Builder")
    print("=" * 50)

    # Step 1: Load documents
    print(f"\n[Step 1] Loading documents{f' for company: {company_name}' if company_name else ''}...")
    documents = load_documents(company_name=company_name)

    if not documents:
        print("[IndexBuilder] No documents found. Add PDFs or TXTs to company_docs/")
        print("Expected structure:")
        print("  company_docs/")
        print("    Google/")
        print("      job_description.pdf")
        print("      tech_stack.txt")
        print("    Amazon/")
        print("      requirements.pdf")
        return False

    # Step 2: Split into chunks
    print(f"\n[Step 2] Splitting {len(documents)} document(s) into chunks...")
    chunks = split_documents(documents)

    if not chunks:
        print("[IndexBuilder] Splitting produced no chunks.")
        return False

    # Step 3 & 4: Embed and store
    if not rebuild and index_exists():
        # Merge new chunks into the existing index
        print(f"\n[Step 3-4] Merging {len(chunks)} new chunks into existing index...")
        try:
            from rag.embeddings import get_embedding_model
            existing_store = load_vector_store()
            embedding_model = get_embedding_model()
            new_store = FAISS.from_documents(chunks, embedding_model)
            existing_store.merge_from(new_store)

            from rag.vector_store import VECTOR_STORE_DIR, INDEX_NAME
            existing_store.save_local(VECTOR_STORE_DIR, index_name=INDEX_NAME)
            print("[IndexBuilder] Merged and saved updated index.")
        except Exception as e:
            print(f"[IndexBuilder] Merge failed: {e}. Rebuilding from scratch...")
            build_vector_store(chunks)
    else:
        # Build fresh index
        print(f"\n[Step 3-4] Embedding {len(chunks)} chunks and building FAISS index...")
        build_vector_store(chunks)

    print("\n[IndexBuilder] ✓ Index built successfully.")
    print(f"[IndexBuilder] Total chunks indexed: {len(chunks)}")
    print("=" * 50 + "\n")
    return True


def verify_index(topic: str = "Python", company_name: str = None):
    """
    Quick verification — retrieves sample results to confirm index works.

    Args:
        topic: Test query topic.
        company_name: Optional company filter.
    """
    print("\n[Verify] Testing retrieval...")
    from rag.retriever import retrieve_context
    context = retrieve_context(topic=topic, company_name=company_name)

    if context:
        print(f"[Verify] ✓ Retrieval successful. Sample context:\n")
        print(context[:500] + "..." if len(context) > 500 else context)
    else:
        print("[Verify] No context retrieved. Check your documents and index.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build RAG index from company documents.")
    parser.add_argument("--company", type=str, default=None, help="Index only this company's docs")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild index from scratch")
    parser.add_argument("--verify", action="store_true", help="Run a test retrieval after building")
    parser.add_argument("--topic", type=str, default="Python", help="Topic to use for verification")

    args = parser.parse_args()

    success = build_index(company_name=args.company, rebuild=args.rebuild)

    if success and args.verify:
        verify_index(topic=args.topic, company_name=args.company)
