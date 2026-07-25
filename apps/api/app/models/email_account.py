import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.email_thread import EmailThread


class EmailProvider(enum.StrEnum):
    GMAIL = "gmail"
    # Phase 3 (docs/EMAIL_INTELLIGENCE.md): mock-connector-sourced test email,
    # ingested through the same EmailAccount/EmailThread/EmailMessage schema as
    # a real Gmail account so the rest of the pipeline (classification,
    # extraction, drafting) doesn't need a parallel code path. No real OAuth
    # token exists for this row — `refresh_token_encrypted` is a placeholder,
    # never used for an actual token exchange.
    MOCK = "mock"


class EmailAccount(Base):
    """A connected mailbox (docs/MVP_SCOPE.md feature 1: Gmail-first for MVP).

    `refresh_token_encrypted` is the highest-sensitivity secret in the system
    (docs/SYSTEM_ARCHITECTURE.md §4) — always written/read through
    app/core/crypto.py, never handled as plaintext outside that module.

    `integration_id` points at the generic `integrations` registry row for this
    connection; this table holds the Gmail-specific detail (encrypted token,
    history cursor) per docs/DATABASE_DESIGN.md §3.
    """

    __tablename__ = "email_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "email_address", name="uq_email_account_org_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[EmailProvider] = mapped_column(
        Enum(EmailProvider, name="email_provider"), nullable=False, default=EmailProvider.GMAIL
    )
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    # Gmail's sync cursor: the historyId to resume incremental sync from.
    # Null until the first full sync has completed.
    history_cursor: Mapped[str | None] = mapped_column(String(64), nullable=True)

    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    threads: Mapped[list["EmailThread"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
