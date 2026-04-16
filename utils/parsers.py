"""
utils/parsers.py
────────────────
File extraction utilities.
Priority:
  - PDF  → PyMuPDF (fitz)
  - Excel → pandas
  - Image → Tesseract OCR (local), fallback to Gemini Vision
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd

# ── PDF ──────────────────────────────────────────────────────────────────────
def extract_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        texts = [page.get_text() for page in doc]
        return "\n\n".join(texts).strip()
    except Exception as e:
        return f"[PDF extraction error: {e}]"


# ── Excel / CSV ───────────────────────────────────────────────────────────────
def extract_excel(file_bytes: bytes, filename: str) -> str:
    """Parse Excel or CSV and return a text representation."""
    try:
        ext = Path(filename).suffix.lower()
        buf = io.BytesIO(file_bytes)
        if ext == ".csv":
            df = pd.read_csv(buf)
        else:
            df = pd.read_excel(buf, sheet_name=None)
            if isinstance(df, dict):
                parts = []
                for sheet, sdf in df.items():
                    parts.append(f"### Sheet: {sheet}\n{sdf.to_string(index=False)}")
                return "\n\n".join(parts)
        return df.to_string(index=False)
    except Exception as e:
        return f"[Excel/CSV extraction error: {e}]"


# ── Image (Tesseract → Gemini fallback) ──────────────────────────────────────
def extract_image(file_bytes: bytes, filename: str, gemini_client=None) -> str:
    """
    Extract text from an image.
    1. Try local Tesseract OCR.
    2. On failure, use Gemini Vision API as fallback.
    """
    # ── Tesseract attempt ──
    try:
        import pytesseract
        from PIL import Image

        # Try common install paths on Windows
        tesseract_cmd = os.getenv(
            "TESSERACT_CMD",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        )
        if Path(tesseract_cmd).exists():
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img)
        if text.strip():
            return f"[OCR via Tesseract]\n{text.strip()}"
    except Exception:
        pass  # Fall through to Gemini

    # ── Gemini Vision fallback ──
    if gemini_client:
        try:
            import base64
            import google.generativeai as genai

            ext = Path(filename).suffix.lstrip(".").lower()
            mime_type = f"image/{ext if ext in ('png', 'jpg', 'jpeg', 'webp') else 'png'}"
            img_part = {
                "mime_type": mime_type,
                "data": base64.b64encode(file_bytes).decode(),
            }
            model = genai.GenerativeModel("gemini-2.0-flash-exp")
            resp = model.generate_content([
                "Extract all text from this financial document image. Output raw text only.",
                img_part,
            ])
            return f"[OCR via Gemini Vision]\n{resp.text.strip()}"
        except Exception as e:
            return f"[Image extraction error: {e}]"

    return "[Image extraction failed: Tesseract not found and no Gemini client provided]"


# ── Dispatcher ───────────────────────────────────────────────────────────────
def extract_file(file_bytes: bytes, filename: str, gemini_client=None) -> str:
    """Route to the correct extractor based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_pdf(file_bytes)
    elif ext in (".xlsx", ".xls", ".csv"):
        return extract_excel(file_bytes, filename)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp"):
        return extract_image(file_bytes, filename, gemini_client)
    else:
        # Best-effort: try to decode as text
        try:
            return file_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            return f"[Unknown file type {ext}: {e}]"
