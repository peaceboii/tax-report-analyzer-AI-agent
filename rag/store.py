"""
rag/store.py
─────────────
Efficient FAISS-backed vector store for tax documents and chat summaries.
Uses Google Generative AI for embeddings.
"""

from __future__ import annotations

import os
import gc
import shutil
from pathlib import Path
from typing import List, Optional, Dict

import streamlit as st
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

_EMBED_MODEL = "models/text-embedding-004"


class VectorStore:
    """Lightweight FAISS-backed vector store with Google embedding support."""

    def __init__(self, persist_dir: str = "./data/faiss_index"):
        self.persist_path = Path(persist_dir)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        # Paths for separate indices
        self.doc_index_path = self.persist_path / "documents"
        self.mem_index_path = self.persist_path / "memory"
        
        # Lazy indices
        self._doc_db: Optional[FAISS] = None
        self._mem_db: Optional[FAISS] = None
        self._embedder: Optional[GoogleGenerativeAIEmbeddings] = None

    # ── Private helpers ────────────────────────────────────────────────────
    def _get_embedder(self) -> GoogleGenerativeAIEmbeddings:
        if self._embedder is None:
            self._embedder = GoogleGenerativeAIEmbeddings(
                model=_EMBED_MODEL,
                google_api_key=os.getenv("GOOGLE_API_KEY"),
            )
        return self._embedder

    def _get_db(self, index_path: Path) -> Optional[FAISS]:
        """Loads a FAISS index from disk or returns None if it doesn't exist."""
        if not index_path.exists() or not (index_path / "index.faiss").exists():
            return None
        try:
            return FAISS.load_local(
                str(index_path), 
                self._get_embedder(), 
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            st.warning(f"Failed to load index at {index_path.name}: {e}")
            return None

    # ── Document methods ───────────────────────────────────────────────────
    def add_chunks(
        self,
        chunks: list[str],
        filename: str,
        source_id: str,
        user_id: str,
    ) -> None:
        """Add chunks to store in batches to minimize RAM spikes."""
        if not chunks:
            return

        batch_size = 50
        total = len(chunks)
        
        # Initialize or load existing doc DB
        db = self._get_db(self.doc_index_path)

        for i in range(0, total, batch_size):
            batch_text = chunks[i : i + batch_size]
            batch_metas = [
                {"filename": filename, "source_id": source_id, "chunk_idx": j, "user_id": user_id} 
                for j in range(i, i + len(batch_text))
            ]
            
            if db is None:
                db = FAISS.from_texts(batch_text, self._get_embedder(), metadatas=batch_metas)
            else:
                db.add_texts(batch_text, metadatas=batch_metas)
            
            # Frequent cleanup
            gc.collect()

        # Save back to disk
        if db:
            db.save_local(str(self.doc_index_path))
            self._doc_db = db

    def search_docs(self, query: str, user_id: str, k: int = 5) -> list[dict]:
        """Search document chunks matching the user_id."""
        db = self._get_db(self.doc_index_path)
        if not db:
            return []

        # FAISS uses post-filtering in LangChain. fetch_k=50 increases chance of hits for specific users.
        results = db.similarity_search(
            query, 
            k=k, 
            filter={"user_id": user_id},
            fetch_k=max(k * 10, 50)
        )
        
        output = []
        for doc in results:
            output.append({
                "content": doc.page_content,
                "metadata": doc.metadata
            })
        return output

    # ── Memory methods ─────────────────────────────────────────────────────
    def add_memory(self, text: str, user_id: str, session_id: str) -> None:
        """Add a summary or memory context to the database."""
        db = self._get_db(self.mem_index_path)
        meta = {"user_id": user_id, "session_id": session_id}
        
        if db is None:
            db = FAISS.from_texts([text], self._get_embedder(), metadatas=[meta])
        else:
            db.add_texts([text], metadatas=[meta])
        
        db.save_local(str(self.mem_index_path))
        self._mem_db = db

    def search_memory(self, query: str, user_id: str, k: int = 3) -> str:
        """Retrieve relevant past memories for a user."""
        db = self._get_db(self.mem_index_path)
        if not db:
            return ""

        results = db.similarity_search(
            query, 
            k=k, 
            filter={"user_id": user_id},
            fetch_k=max(k * 5, 20)
        )
        return "\n".join([d.page_content for d in results])

    def clear_session_docs(self, user_id: str, source_id: str) -> None:
        """
        Removes documents for a specific source.
        Note: FAISS handles deletion by recreating the index without the target docs.
        """
        db = self._get_db(self.doc_index_path)
        if not db:
            return
            
        # Extract all internal FAISS IDs that DON'T match this source
        filtered_docs = []
        for _, doc in db.docstore._dict.items():
            if doc.metadata.get("source_id") != source_id or doc.metadata.get("user_id") != user_id:
                filtered_docs.append(doc)
        
        if not filtered_docs:
            if self.doc_index_path.exists():
                shutil.rmtree(self.doc_index_path)
            self._doc_db = None
        else:
            new_db = FAISS.from_documents(filtered_docs, self._get_embedder())
            new_db.save_local(str(self.doc_index_path))
            self._doc_db = new_db
