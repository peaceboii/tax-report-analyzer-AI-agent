"""
rag/store.py
─────────────
Persistent ChromaDB vector store for tax documents and chat summaries.
Embeddings via Google Generative AI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

_EMBED_MODEL = "models/embedding-001"


class VectorStore:
    """Persistent ChromaDB-backed vector store with Google embedding support."""

    def __init__(self, persist_dir: str = "./data/chroma_db"):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        # Persistent client – survives restarts
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )

        # Separate collections for document chunks vs chat memories
        self._docs = self._client.get_or_create_collection("tax_documents")
        self._memory = self._client.get_or_create_collection("chat_memory")

        # Embedding function (lazy init)
        self._embedder: Optional[GoogleGenerativeAIEmbeddings] = None

    # ── Private helpers ────────────────────────────────────────────────────
    def _get_embedder(self) -> GoogleGenerativeAIEmbeddings:
        if self._embedder is None:
            self._embedder = GoogleGenerativeAIEmbeddings(
                model=_EMBED_MODEL,
                google_api_key=os.getenv("GOOGLE_API_KEY"),
            )
        return self._embedder

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return self._get_embedder().embed_documents(texts)

    # ── Document methods ───────────────────────────────────────────────────
    def add_chunks(
        self,
        chunks: list[str],
        filename: str,
        source_id: str,
        user_id: str,
    ) -> None:
        """Add document text chunks to the vector store, scoped to user."""
        if not chunks:
            return

        embeddings = self._embed(chunks)
        ids = [f"{source_id}_{i}" for i in range(len(chunks))]
        metadatas = [{"filename": filename, "source_id": source_id, "chunk_idx": i, "user_id": user_id}
                     for i in range(len(chunks))]

        self._docs.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

    def search_docs(self, query: str, user_id: str, k: int = 5) -> list[dict]:
        """Search document chunks matching the user_id."""
        if self._docs.count() == 0:
            return []

        q_emb = self._get_embedder().embed_query(query)
        results = self._docs.query(
            query_embeddings=[q_emb],
            n_results=min(k, self._docs.count()),
            where={"user_id": user_id}
        )
        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({"text": doc, "metadata": meta, "score": round(1 - dist, 4)})
        return output

    def list_documents(self, user_id: str) -> list[str]:
        """Return list of unique filenames stored for this user."""
        if self._docs.count() == 0:
            return []
        try:
            meta = self._docs.get(where={"user_id": user_id}, include=["metadatas"])["metadatas"]
            seen = {}
            for m in meta:
                if "source_id" in m and "filename" in m:
                    seen[m["source_id"]] = m["filename"]
            return list(seen.values())
        except Exception:
            return []

    def clear_documents(self) -> None:
        """Remove all document chunks."""
        self._client.delete_collection("tax_documents")
        self._docs = self._client.get_or_create_collection("tax_documents")

    # ── Memory methods ─────────────────────────────────────────────────────
    def add_memory(self, summary: str, memory_id: str, user_id: str) -> None:
        """Store a compressed chat summary, scoped to user."""
        emb = self._embed([summary])
        self._memory.upsert(
            ids=[memory_id],
            embeddings=emb,
            documents=[summary],
            metadatas=[{"user_id": user_id}]
        )

    def search_memory(self, query: str, user_id: str, k: int = 3) -> list[str]:
        """Retrieve relevant past conversation summaries for user."""
        if self._memory.count() == 0:
            return []
        try:
            q_emb = self._get_embedder().embed_query(query)
            results = self._memory.query(
                query_embeddings=[q_emb],
                n_results=min(k, self._memory.count()),
                where={"user_id": user_id}
            )
            return results["documents"][0] if results["documents"] else []
        except Exception:
            return []
