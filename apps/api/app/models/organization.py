import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Organization(Base):
    """A single deployed customer per docs/SYSTEM_ARCHITECTURE.md §7 (self-hosted, single-tenant v1).

    organization_id is still carried on every downstream table so a later move
    to multi-tenant SaaS is a topology change, not a schema rewrite. Named
    `Organization` rather than `Workspace` per docs/DATABASE_DESIGN.md §1.
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
