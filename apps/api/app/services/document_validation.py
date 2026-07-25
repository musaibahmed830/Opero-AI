"""File validation and safe-filename handling (docs/KNOWLEDGE_SYSTEM.md,
docs/SECURITY_MODEL.md §"File-type validation" / "Path traversal protection").

`generate_safe_filename` never derives any part of the storage path from the
user-supplied original filename — it's a fresh UUID plus a normalized
extension pulled from an allowlist, not a sanitized version of the input.
That's what actually prevents path traversal (`../../etc/passwd`) and null-byte
tricks, rather than trying to blocklist dangerous characters after the fact.
"""

import hashlib
import uuid

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
}


class UnsupportedFileTypeError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


def _extension_of(filename: str) -> str:
    lowered = filename.lower()
    for ext in ALLOWED_EXTENSIONS:
        if lowered.endswith(ext):
            return ext
    return ""


def validate_file_type(original_filename: str) -> str:
    """Returns the normalized extension, or raises UnsupportedFileTypeError."""
    ext = _extension_of(original_filename)
    if not ext:
        supported = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UnsupportedFileTypeError(
            f"Unsupported file type for '{original_filename}'. Supported: {supported}"
        )
    return ext


def validate_file_size(size_bytes: int, max_bytes: int) -> None:
    if size_bytes > max_bytes:
        raise FileTooLargeError(
            f"File is {size_bytes} bytes, which exceeds the {max_bytes}-byte limit."
        )
    if size_bytes == 0:
        raise FileTooLargeError("File is empty.")


def generate_safe_filename(extension: str) -> str:
    return f"{uuid.uuid4().hex}{extension}"


def compute_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
