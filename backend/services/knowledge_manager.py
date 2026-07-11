"""
services/knowledge_manager.py
------------------------------
Orchestrates the full RAG pipeline:
  - Document parsing (PDF, TXT)
  - Text splitting (RecursiveCharacterTextSplitter)
  - Vector index creation and merging (FAISS via VectorStoreService)
  - Metadata tracking and priority-based context retrieval

Integrates with SQLite database and storage modules to maintain persistent mappings.
"""

import os
import pypdf
from typing import Optional, List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from config import (
    CHUNK_SIZE, CHUNK_OVERLAP, CHUNK_SEPARATORS, TOP_K_RETRIEVAL,
    PRIORITY_UPLOADED_JD, PRIORITY_UPLOADED_DOCS, PRIORITY_DEFAULT_COMPANY,
    PRIORITY_GENERAL
)
from logger import get_logger
from services.vector_store_service import vector_store_service
from services.embedding_service import embedding_service
import database
import storage

logger = get_logger(__name__)


class KnowledgeManager:
    """
    Manages custom and shared company knowledge vector store files and queries.
    """

    def _parse_file(self, filepath: str) -> List[Document]:
        """
        Parses a file from disk into a list of LangChain Document objects.
        Supports PDF and TXT.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        ext = filepath.rsplit(".", 1)[-1].lower()
        documents = []
        filename = os.path.basename(filepath)

        try:
            if ext == "pdf":
                logger.info("Parsing PDF file: %s", filename)
                with open(filepath, "rb") as f:
                    reader = pypdf.PdfReader(f)
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text()
                        if text and text.strip():
                            doc = Document(
                                page_content=text,
                                metadata={
                                    "source": filename,
                                    "page": i + 1
                                }
                            )
                            documents.append(doc)
            elif ext == "docx" or ext == "doc":
                logger.info("Parsing DOCX/DOC file: %s", filename)
                import docx2txt
                text = docx2txt.process(filepath)
                if text.strip():
                    doc = Document(
                        page_content=text,
                        metadata={"source": filename}
                    )
                    documents.append(doc)
            elif ext == "txt":
                logger.info("Parsing TXT file: %s", filename)
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                    if text.strip():
                        doc = Document(
                            page_content=text,
                            metadata={"source": filename}
                        )
                        documents.append(doc)
            else:
                logger.warning("Unsupported file type for parsing: %s", ext)
                raise ValueError(f"Unsupported file format: {ext}")
        except Exception as e:
            logger.error("Failed to parse file %s: %s", filepath, e, exc_info=True)
            raise RuntimeError(f"Failed to parse document: {e}") from e

        return documents

    def _split_text(self, documents: List[Document]) -> List[Document]:
        """
        Splits parsed Document objects into overlapping chunks using RecursiveCharacterTextSplitter.
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=CHUNK_SEPARATORS,
            length_function=len,
        )
        chunks = splitter.split_documents(documents)
        logger.info("Split %d documents into %d chunks", len(documents), len(chunks))
        return chunks

    def ingest_document(self, session_id: str, stored_path: str, original_filename: str, doc_type: str) -> dict:
        """
        Loads, splits, embeds, and saves a custom document into the session's FAISS index.
        Merges with any existing session index if present.

        Args:
            session_id: The ID of the current interview session.
            stored_path: Absolute path to the uploaded file on disk.
            original_filename: The human-readable name of the file.
            doc_type: Either 'jd', 'notes', or 'general'.

        Returns:
            Dict containing stats of ingestion (doc_count, chunk_count).
        """
        # Step 1: Parse
        raw_docs = self._parse_file(stored_path)
        if not raw_docs:
            raise ValueError("No readable text could be extracted from the file.")

        # Step 2: Inject metadata details to chunks
        for doc in raw_docs:
            doc.metadata["doc_type"] = doc_type
            doc.metadata["original_name"] = original_filename

        # Step 3: Split
        chunks = self._split_text(raw_docs)
        if not chunks:
            raise ValueError("Document splitting produced 0 chunks.")

        vectors_dir = storage.get_session_vectors_dir(session_id)
        os.makedirs(vectors_dir, exist_ok=True)

        # Step 4: Build or merge index
        if vector_store_service.session_index_exists(session_id):
            logger.info("Session vector index exists. Merging new chunks for session %s", session_id)
            try:
                existing_store = vector_store_service.load_session_index(session_id)
                new_store = FAISS.from_documents(chunks, embedding_service.model)
                existing_store.merge_from(new_store)
                existing_store.save_local(vectors_dir, index_name="session_index")
                vector_store_service._cache_store(session_id, existing_store)
                logger.info("Merged vector store for session %s successfully", session_id)
            except Exception as e:
                logger.warning("Failed to merge index: %s. Rebuilding from scratch...", e)
                # Fallback: Build new FAISS index from the chunks directly
                vector_store_service.build_session_index(session_id, chunks)
        else:
            logger.info("Creating new session vector index for session %s", session_id)
            vector_store_service.build_session_index(session_id, chunks)

        # Step 5: Save database mappings
        doc_count = len(raw_docs)
        chunk_count = len(chunks)
        
        # Save vector path metadata in SQLite database
        database.save_vector_path(
            session_id=session_id,
            vector_path=vectors_dir,
            doc_count=doc_count,
            chunk_count=chunk_count
        )

        return {
            "doc_count": doc_count,
            "chunk_count": chunk_count,
            "status": "success"
        }

    def retrieve_context(self, session_id: str, query: str, company: Optional[str] = None) -> str:
        """
        Performs semantic similarity search across custom session documents and default company profiles.
        Sorts the combined matches using priority weights to build the RAG context block.
        """
        candidates: List[Document] = []

        # 1. Fetch custom session documents
        if vector_store_service.session_index_exists(session_id):
            try:
                session_store = vector_store_service.load_session_index(session_id)
                session_matches = vector_store_service.similarity_search(
                    session_store, query, k=TOP_K_RETRIEVAL
                )
                candidates.extend(session_matches)
                logger.info("Retrieved %d context chunks from session store", len(session_matches))
            except Exception as e:
                logger.error("Error retrieving context from session index: %s", e)

        # 2. Fetch default company documents
        if company and vector_store_service.default_index_exists(company):
            try:
                company_store = vector_store_service.load_default_index(company)
                if company_store:
                    company_matches = vector_store_service.similarity_search(
                        company_store, query, k=TOP_K_RETRIEVAL
                    )
                    # Label default documents if they do not have doc_type set
                    for doc in company_matches:
                        if "doc_type" not in doc.metadata:
                            doc.metadata["doc_type"] = "company"
                        if "company" not in doc.metadata:
                            doc.metadata["company"] = company
                    candidates.extend(company_matches)
                    logger.info("Retrieved %d context chunks from default company store: %s", len(company_matches), company)
            except Exception as e:
                logger.error("Error retrieving context from default company index: %s", e)

        if not candidates:
            logger.info("No context chunks retrieved for query: '%s'", query)
            return ""

        # 3. Define priority weights sorting strategy
        def get_priority_weight(doc: Document) -> int:
            doc_type = doc.metadata.get("doc_type", "general")
            if doc_type == "jd":
                return PRIORITY_UPLOADED_JD
            elif doc_type == "notes":
                return PRIORITY_UPLOADED_DOCS
            elif doc_type == "company":
                return PRIORITY_DEFAULT_COMPANY
            else:
                return PRIORITY_GENERAL

        # Sort candidates: Higher priority weights first
        candidates.sort(key=get_priority_weight, reverse=True)

        # Limit to top k matches
        top_candidates = candidates[:TOP_K_RETRIEVAL]

        # 4. Format into context blocks
        context_parts = []
        for i, doc in enumerate(top_candidates, 1):
            source = doc.metadata.get("original_name") or doc.metadata.get("source") or "unknown"
            doc_type = doc.metadata.get("doc_type", "general")
            context_parts.append(
                f"[Context {i} | Source: {source} | Type: {doc_type}]\n"
                f"{doc.page_content.strip()}"
            )

        formatted_context = "\n\n".join(context_parts)
        logger.info("Formatted %d context chunks for prompt injection", len(top_candidates))
        return formatted_context


# Singleton instance
knowledge_manager = KnowledgeManager()
