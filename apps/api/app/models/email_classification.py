import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailCategory(enum.StrEnum):
    SALES = "sales"
    SUPPORT = "support"
    COMPLAINT = "complaint"
    BILLING = "billing"
    PROJECT = "project"
    MEETING = "meeting"
    INTERNAL = "internal"
    NEWSLETTER = "newsletter"
    SPAM = "spam"
    OTHER = "other"


class EmailPriority(enum.StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EmailSentiment(enum.StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class EmailClassification(Base):
    """The AI-derived analysis layer for an email — deliberately a separate
    table from `EmailMessage` (docs/EMAIL_INTELLIGENCE.md §"Email
    classification"): `EmailMessage` is the raw ingested fact, this is a model
    opinion about it. Keeping them separate means re-classifying (a better
    prompt, a different model) never touches the ingested data, and every
    classification is independently auditable.

    `priority` (how important) and `urgency` (how time-sensitive) are
    deliberately distinct dimensions — a newsletter can never be urgent
    regardless of priority, and a low-priority request can still be urgent if
    it names a deadline. Both use the same four-point scale for simplicity.
    """

    __tablename__ = "email_classifications"
    __table_args__ = (UniqueConstraint("message_id", name="uq_email_classification_message"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[EmailCategory] = mapped_column(
        Enum(EmailCategory, name="email_category"), nullable=False
    )
    priority: Mapped[EmailPriority] = mapped_column(
        Enum(EmailPriority, name="email_priority"), nullable=False
    )
    urgency: Mapped[EmailPriority] = mapped_column(
        Enum(EmailPriority, name="email_priority"), nullable=False
    )
    sentiment: Mapped[EmailSentiment] = mapped_column(
        Enum(EmailSentiment, name="email_sentiment"), nullable=False
    )

    requires_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contains_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contains_task: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contains_deadline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contains_payment_issue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    possible_spam: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    possible_prompt_injection: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    short_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_model_output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
