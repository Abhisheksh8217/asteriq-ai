"""
rag/
----
RAG (Retrieval-Augmented Generation) package for company-specific interviews.

Modules:
    loader        — Load PDF/TXT documents from company_docs/
    splitter      — Chunk documents using RecursiveCharacterTextSplitter
    embeddings    — Google Generative AI embedding model
    vector_store  — FAISS index creation, persistence, and loading
    retriever     — Query vector store and return formatted context
    index_builder — CLI entry point to build/rebuild the FAISS index
"""
