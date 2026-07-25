"""Document ingestion pipeline (docs/KNOWLEDGE_SYSTEM.md).

`create_document` (upload) and `process_document` (extract -> clean -> chunk ->
embed -> store) are deliberately separate steps: upload must respond quickly
and dedupe by checksum before anything expensive happens; processing runs in
the background (app/workers/tasks.py) and is retried independently of the
upload request.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.audit_log import AuditActorType, AuditLog
from app.models.document import Document, DocumentProcessingStatus
from app.models.document_chunk import DocumentChunk
from app.services.ai_provider import get_model_provider
from app.services.chunking import chunk_text
from app.services.document_validation import (
    compute_checksum,
    generate_safe_filename,
    validate_file_size,
    validate_file_type,
)
from app.services.storage import download_bytes, upload_bytes
from app.services.text_extraction import TextExtractionError, clean_text, extract_text


class DuplicateDocumentError(Exception):
    def __init__(self, existing_document_id: uuid.UUID) -> None:
        self.existing_document_id = existing_document_id
        super().__init__(f"Duplicate document — matches existing document {existing_document_id}.")


async def create_document(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    uploaded_by: uuid.UUID | None,
    original_filename: str,
    content: bytes,
    content_type: str,
) -> Document:
    """Validates, dedupes, stores the file, and creates the Document row with
    status=uploaded. Does not extract/chunk/embed — see `process_document`.
    """
    settings = get_settings()
    extension = validate_file_type(original_filename)
    validate_file_size(len(content), settings.max_document_size_bytes)
    checksum = compute_checksum(content)

    existing = await db.execute(
        select(Document).where(
            Document.organization_id == organization_id, Document.checksum == checksum
        )
    )
    existing_document = existing.scalar_one_or_none()
    if existing_document is not None:
        raise DuplicateDocumentError(existing_document.id)

    safe_filename = generate_safe_filename(extension)
    storage_path = upload_bytes(f"{organization_id}/{safe_filename}", content, content_type)

    document = Document(
        organization_id=organization_id,
        uploaded_by=uploaded_by,
        title=original_filename,
        original_filename=original_filename,
        safe_filename=safe_filename,
        mime_type=content_type,
        file_size=len(content),
        checksum=checksum,
        storage_path=storage_path,
        processing_status=DocumentProcessingStatus.UPLOADED,
    )
    db.add(document)
    await db.flush()

    db.add(
        AuditLog(
            organization_id=organization_id,
            actor_type=AuditActorType.USER,
            actor_id=uploaded_by,
            action="document.uploaded",
            resource_type="document",
            resource_id=document.id,
            audit_metadata={"original_filename": original_filename, "file_size": len(content)},
        )
    )
    await db.commit()
    await db.refresh(document)
    return document


def _extension_from_safe_filename(safe_filename: str) -> str:
    dot = safe_filename.rfind(".")
    return safe_filename[dot:] if dot != -1 else ""


async def process_document(db: AsyncSession, document: Document) -> None:
    """Extract -> clean -> chunk -> embed -> store. Updates `document` in place
    and commits. Any failure is caught, recorded on the document
    (`processing_status=failed`, `processing_error`), and re-raised so the
    caller (a Celery task) can apply its own retry policy.
    """
    settings = get_settings()
    document.processing_status = DocumentProcessingStatus.PROCESSING
    await db.commit()

    try:
        content = download_bytes(document.storage_path)
        extension = _extension_from_safe_filename(document.safe_filename)
        raw_text = extract_text(content, extension)
        cleaned = clean_text(raw_text)

        if not cleaned:
            raise TextExtractionError("No text could be extracted from this document.")

        chunks = chunk_text(
            cleaned,
            chunk_size=settings.chunk_size_chars,
            chunk_overlap=settings.chunk_overlap_chars,
            min_chunk_length=settings.min_chunk_length_chars,
        )
        if not chunks:
            raise TextExtractionError("Extracted text produced no usable chunks.")

        provider = get_model_provider()
        embeddings = await provider.embed([c.text for c in chunks])

        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    organization_id=document.organization_id,
                    chunk_index=index,
                    content=chunk.text,
                    token_estimate=chunk.token_estimate,
                    embedding=embedding,
                )
            )

        document.processing_status = DocumentProcessingStatus.READY
        document.processed_at = datetime.now(UTC)
        document.processing_error = None

        db.add(
            AuditLog(
                organization_id=document.organization_id,
                actor_type=AuditActorType.SYSTEM,
                actor_id=None,
                action="document.processed",
                resource_type="document",
                resource_id=document.id,
                audit_metadata={"chunk_count": len(chunks)},
            )
        )
        await db.commit()

    except Exception as exc:
        await db.rollback()
        document.processing_status = DocumentProcessingStatus.FAILED
        document.processing_error = str(exc)
        db.add(
            AuditLog(
                organization_id=document.organization_id,
                actor_type=AuditActorType.SYSTEM,
                actor_id=None,
                action="document.failed",
                resource_type="document",
                resource_id=document.id,
                audit_metadata={"error": str(exc)},
            )
        )
        await db.commit()
        raise


async def archive_document(db: AsyncSession, document: Document, *, archived_by: uuid.UUID) -> Document:
    document.processing_status = DocumentProcessingStatus.ARCHIVED
    document.archived_at = datetime.now(UTC)

    db.add(
        AuditLog(
            organization_id=document.organization_id,
            actor_type=AuditActorType.USER,
            actor_id=archived_by,
            action="document.archived",
            resource_type="document",
            resource_id=document.id,
            audit_metadata={},
        )
    )
    await db.commit()
    await db.refresh(document)
    return document
