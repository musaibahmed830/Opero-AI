import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApprovalStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    # Phase 3 additions (docs/APPROVAL_WORKFLOW.md):
    EDITED = "edited"  # user saved an edit but hasn't approved/rejected yet
    EXPIRED = "expired"  # left pending past a TTL — nothing was auto-approved
    CANCELLED = "cancelled"  # withdrawn (e.g. the underlying email thread went stale)


class ApprovalRequest(Base):
    """The approval gate (docs/SECURITY_MODEL.md §5): no external, irreversible
    action executes without a row here reaching `approved`. Phase 2 built the
    full propose -> review -> decide -> audit loop with no downstream
    execution. Phase 3 wires a real proposer (draft generation) and a real —
    but simulated — downstream action (docs/EMAIL_INTELLIGENCE.md): approving
    a `send_email_reply` request calls the mock connector's send method and
    records the (fake) result here, never a real send.

    `payload` is always the original, AI-generated proposal — never mutated
    after creation, so "what did the AI actually produce" stays inspectable.
    `resolved_payload` is null until a decision is made; on approval (with or
    without edits) it holds the exact content that was "sent" — edited or not.
    """

    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ai_employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    resolved_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    simulated_send_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status"), nullable=False, default=ApprovalStatus.PENDING
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
