"""
loader.py
---------
Responsible for loading documents from the company_docs directory.
Supports PDF, TXT, and DOCX formats.
Each document is tagged with metadata (source filename, company name)
so the retriever can filter by company during interviews.
"""

import os
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document


# Absolute path to the company_docs folder relative to this file
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "company_docs")


def load_documents(company_name: str = None) -> list[Document]:
    """
    Load all supported documents from the company_docs directory.

    Args:
        company_name: Optional filter — loads only docs inside a
                      subdirectory matching the company name.
                      If None, loads all documents from all companies.

    Returns:
        List of LangChain Document objects with metadata attached.
    """
    documents = []

    # Determine the root directory to scan
    scan_dir = (
        os.path.join(DOCS_DIR, company_name)
        if company_name
        else DOCS_DIR
    )

    if not os.path.exists(scan_dir):
        print(f"[Loader] Directory not found: {scan_dir}")
        return []

    for root, _, files in os.walk(scan_dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            ext = filename.lower().split(".")[-1]

            try:
                if ext == "pdf":
                    loader = PyPDFLoader(filepath)
                    docs = loader.load()

                elif ext == "txt":
                    loader = TextLoader(filepath, encoding="utf-8")
                    docs = loader.load()

                else:
                    # Skip unsupported formats silently
                    continue

                # Attach company metadata to every page/chunk
                company = os.path.basename(root) if company_name is None else company_name
                for doc in docs:
                    doc.metadata["source"] = filename
                    doc.metadata["company"] = company

                documents.extend(docs)
                print(f"[Loader] Loaded {len(docs)} page(s) from: {filename}")

            except Exception as e:
                print(f"[Loader] Failed to load {filename}: {e}")

    print(f"[Loader] Total documents loaded: {len(documents)}")
    return documents
