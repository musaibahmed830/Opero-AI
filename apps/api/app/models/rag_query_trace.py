import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RagQueryTrace(Base):
    """One row per knowledge question asked (docs/RAG_PIPELINE.md). Exists so
    every AI-generated answer is auditable after the fact: what was asked, what
    was retrieved, what the model said, and whether anything about the
    retrieved content looked like a prompt-injection attempt
    (docs/PROMPT_INJECTION_DEFENCE.md).
    """

    __tablename__ = "rag_query_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    insufficient_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    generation_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_injection_flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
