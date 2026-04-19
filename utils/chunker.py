"""
utils/chunker.py
────────────────
Robust text chunking utilities for RAG ingestion.
Fixed to avoid infinite loops on small inputs.
"""

from __future__ import annotations


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[str]:
    """
    Split `text` into overlapping chunks of `chunk_size` characters.
    Ensures the loop always advances to avoid hangs.
    """
    text = text.strip()
    if not text:
        return []

    # Safety check: overlap must be smaller than chunk_size
    if overlap >= chunk_size:
        overlap = chunk_size // 2

    chunks: list[str] = []
    length = len(text)
    start = 0

    while start < length:
        # Calculate standard end
        end = min(start + chunk_size, length)

        # Smart boundary snapping (only if we aren't at the very end)
        if end < length:
            # Look for a boundary in the last 20% of the chunk
            search_start = max(start + (chunk_size // 2), start)
            for boundary in ("\n\n", "\n", ". ", "! ", "? "):
                snap = text.rfind(boundary, search_start, end)
                if snap != -1:
                    end = snap + len(boundary)
                    break

        # Extract and store
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # IMPORTANT: Ensure loop always advances
        # If we reached the end, we're done
        if end >= length:
            break
        
        # Next start point (guaranteed to advance since overlap < chunk_size)
        next_start = end - overlap
        
        # Final safety check to avoid infinite loop or backward jumping
        if next_start <= start:
            start = end
        else:
            start = next_start
            
        # Hard limit to prevent catastrophic hangs (max 50,000 chunks)
        if len(chunks) > 50000:
            break

    return chunks
