import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DailyReport(Base):
    """Generated once per day, read-only after generation (docs/DATABASE_DESIGN.md §3).

    `metrics` (Phase 3, docs/DAILY_REPORT_ENGINE.md) holds the full structured
    breakdown the founder's spec asks for (emails by category, unresolved
    critical items, security warnings, etc.) — a JSONB blob rather than ~15
    more named columns, because this report's exact shape is still evolving
    and the well-established top-level counters below already have real
    columns for simple querying. `narrative` is the AI-written prose summary,
    generated only after `metrics` is computed from real stored data — the
    model never invents the numbers (docs/DAILY_REPORT_ENGINE.md
    "Deterministic metrics first").
    """

    __tablename__ = "daily_reports"
    __table_args__ = (UniqueConstraint("organization_id", "report_date", name="uq_daily_report_org_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    emails_handled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    drafts_pending: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leads_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    follow_ups_overdue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tasks_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
