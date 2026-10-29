"""Document Tool: extracts clean text from a supplier PDF (PyMuPDF)."""
from __future__ import annotations

import re

import pymupdf

import config
from domain.models import ExtractionResult


def _clean(text: str) -> str:
    text = text.replace("­", "")                     # soft hyphens
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # words hyphenated across lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(file_bytes: bytes, file_name: str = "document.pdf",
                 max_chars: int = config.MAX_DOCUMENT_CHARS) -> ExtractionResult:
    if not file_bytes:
        return ExtractionResult(ok=False, error=f"{file_name}: file is empty.")
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:  # corrupt / not a PDF
        return ExtractionResult(ok=False, error=f"{file_name}: not a readable PDF ({type(exc).__name__}).")

    with doc:
        if doc.needs_pass:
            return ExtractionResult(ok=False, error=f"{file_name}: PDF is password-protected.")
        pages = [page.get_text("text") for page in doc]
        page_count = doc.page_count

    text = _clean("\n\n".join(pages))
    warnings: list[str] = []
    if len(text) < config.MIN_DOCUMENT_CHARS:
        return ExtractionResult(
            ok=False, pages=page_count, chars=len(text),
            error=(f"{file_name}: only {len(text)} characters of text found across {page_count} page(s). "
                   "The PDF may be scanned or image-only; OCR is not supported."),
        )
    truncated = len(text) > max_chars
    if truncated:
        warnings.append(f"{file_name}: text truncated from {len(text):,} to {max_chars:,} characters.")
        text = text[:max_chars]
    return ExtractionResult(ok=True, text=text, pages=page_count, chars=len(text),
                            truncated=truncated, warnings=warnings)
