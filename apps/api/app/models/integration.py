import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IntegrationProvider(enum.StrEnum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    GOOGLE_CALENDAR = "google_calendar"
    SLACK = "slack"
    CRM = "crm"
    MOCK = "mock"


class IntegrationStatus(enum.StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class Integration(Base):
    """Generic registry row for one connected external account.

    Provider-specific secrets/detail live in their own table (e.g. `EmailAccount`
    for Gmail) referencing this row's id — see docs/DATABASE_DESIGN.md §3 for why
    this stays generic rather than growing provider-specific columns.
    """

    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        Enum(IntegrationProvider, name="integration_provider"), nullable=False
    )
    status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus, name="integration_status"),
        nullable=False,
        default=IntegrationStatus.CONNECTED,
    )
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
