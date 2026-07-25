import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document_chunk import DocumentChunk


class DocumentSourceType(enum.StrEnum):
    UPLOAD = "upload"
    GMAIL_ATTACHMENT = "gmail_attachment"


class DocumentProcessingStatus(enum.StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class Document(Base):
    """Re-ingesting a changed document creates a new version row rather than
    overwriting, so a past decision's grounding document version stays
    inspectable (docs/DATABASE_DESIGN.md §3). Extended in Phase 3
    (docs/KNOWLEDGE_SYSTEM.md) with the full ingestion-pipeline metadata the
    founder's spec requires.

    `checksum` + the unique constraint below is the duplicate-prevention
    mechanism (docs/KNOWLEDGE_SYSTEM.md §"Duplicate prevention"): the same
    exact file content re-uploaded to the same organization is rejected with a
    clear "duplicate" response rather than silently reprocessed.
    """

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "checksum", name="uq_document_org_checksum"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[DocumentSourceType] = mapped_column(
        Enum(DocumentSourceType, name="document_source_type"),
        nullable=False,
        default=DocumentSourceType.UPLOAD,
    )

    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        Enum(DocumentProcessingStatus, name="document_processing_status"),
        nullable=False,
        default=DocumentProcessingStatus.UPLOADED,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index"
    )
