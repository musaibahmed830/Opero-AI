import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user_role import UserRole


class User(Base):
    """Per docs/DATABASE_DESIGN.md §3: role/permission is assigned entirely through
    `user_roles`, not a hardcoded column — see app/models/role.py, permission.py,
    user_role.py.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)

    # MVP auth: local email/password (docs/SECURITY_MODEL.md §3). Nullable because a
    # future SSO-only user (once OIDC is wired up as a second login method) won't have one.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Future SSO: `sub` claim from an external OIDC provider. Nullable/unique — most
    # MVP users will never populate this.
    oidc_subject: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="users")
    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
