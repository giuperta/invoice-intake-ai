"""Turn an uploaded file into plain text for the model."""

from __future__ import annotations

import io

from pypdf import PdfReader


class UnsupportedDocument(ValueError):
    pass


MAX_CHARS = 60_000


def extract_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif name.endswith((".txt", ".md", ".csv")):
        text = content.decode("utf-8", errors="replace")
    else:
        raise UnsupportedDocument("Only PDF and plain-text invoices are supported.")

    text = text.strip()
    if not text:
        raise UnsupportedDocument(
            "No text found in the document (scanned PDFs need OCR first)."
        )
    return text[:MAX_CHARS]
