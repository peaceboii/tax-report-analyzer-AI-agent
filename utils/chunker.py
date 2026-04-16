"""
utils/chunker.py
────────────────
Text chunking utilities for RAG ingestion.
"""

from __future__ import annotations

from typing import Generator


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """
    Split `text` into overlapping chunks of `chunk_size` characters.
    Tries to split at sentence boundaries where possible.
    """
    text = text.strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)

        # Try to snap to a period/newline boundary near `end`
        if end < length:
            for boundary in ("\n\n", "\n", ". ", "! ", "? "):
                snap = text.rfind(boundary, start, end)
                if snap != -1 and snap > start + chunk_size // 2:
                    end = snap + len(boundary)
                    break

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]
