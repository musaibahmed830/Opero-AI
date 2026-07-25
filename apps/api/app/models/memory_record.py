import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Matches the embedding dimension of the Ollama embedding model in
# docs/AI_ARCHITECTURE.md §3 (nomic-embed-text). Revisit if the embedding
# model changes.
EMBEDDING_DIM = 768


class MemoryType(enum.StrEnum):
    SHORT_TERM = "short_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    LONG_TERM_FACT = "long_term_fact"


class MemoryRecord(Base):
    """The four memory layers from docs/SYSTEM_ARCHITECTURE.md §2.3, persisted
    through one table distinguished by `memory_type`. `embedding` is nullable —
    not every memory type needs a vector (a long-term fact might be looked up by
    structured query instead). Storing memory and reasoning over it are
    deliberately separate; see docs/AI_ARCHITECTURE.md §6.
    """

    __tablename__ = "memory_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ai_employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    memory_type: Mapped[MemoryType] = mapped_column(Enum(MemoryType, name="memory_type"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    source_reference: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
