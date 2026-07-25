"""Text extraction for supported document types (docs/KNOWLEDGE_SYSTEM.md).

Local, open-source libraries only — pypdf and python-docx parse document
*structure*, they never execute embedded macros or JavaScript, which is what
keeps a malicious PDF/DOCX's embedded content inert here (docs/SECURITY_MODEL.md
§"Malicious document content isolation"): there is nothing in this module that
evaluates anything from the file, only structural text extraction.
"""

import csv
import io
import re

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.services.document_validation import UnsupportedFileTypeError


class TextExtractionError(Exception):
    pass


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise TextExtractionError(f"Failed to read PDF: {exc}") from exc


def _extract_docx(content: bytes) -> str:
    try:
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    except Exception as exc:
        raise TextExtractionError(f"Failed to read DOCX: {exc}") from exc


def _extract_plain_text(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def _extract_csv(content: bytes) -> str:
    try:
        text = content.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
    except Exception as exc:
        raise TextExtractionError(f"Failed to read CSV: {exc}") from exc

    if not rows:
        return ""

    header, *data_rows = rows
    lines = []
    for row in data_rows:
        pairs = [f"{h.strip()}: {v.strip()}" for h, v in zip(header, row, strict=False) if v.strip()]
        if pairs:
            lines.append(", ".join(pairs))
    return "\n".join(lines)


_EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".txt": _extract_plain_text,
    ".md": _extract_plain_text,
    ".csv": _extract_csv,
}


def extract_text(content: bytes, extension: str) -> str:
    extractor = _EXTRACTORS.get(extension)
    if extractor is None:
        raise UnsupportedFileTypeError(f"No text extractor for '{extension}'.")
    return extractor(content)


_WHITESPACE_RUN = re.compile(r"[ \t]+")
_BLANK_LINE_RUN = re.compile(r"\n{3,}")
_NULL_BYTE = "\x00"


def clean_text(text: str) -> str:
    """Strips null bytes, normalizes line endings, and collapses excess whitespace
    — but never rewrites the substance of the content (docs/KNOWLEDGE_SYSTEM.md
    "Clean extracted text").
    """
    text = text.replace(_NULL_BYTE, "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RUN.sub(" ", text)
    text = _BLANK_LINE_RUN.sub("\n\n", text)
    return text.strip()
