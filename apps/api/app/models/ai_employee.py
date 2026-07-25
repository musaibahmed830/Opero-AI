import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIEmployeeRoleType(enum.StrEnum):
    SALES_OPS_ASSISTANT = "sales_ops_assistant"


class AIEmployeeStatus(enum.StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class AIEmployee(Base):
    """One configured AI employee instance in an organization.

    Only one role type exists today (docs/PRODUCT_REQUIREMENTS.md §3a), but this
    is modeled as its own entity now because Task/ApprovalRequest/Conversation/
    MemoryRecord all need to record which AI employee acted — see
    docs/DATABASE_DESIGN.md §3.
    """

    __tablename__ = "ai_employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_type: Mapped[AIEmployeeRoleType] = mapped_column(
        Enum(AIEmployeeRoleType, name="ai_employee_role_type"),
        nullable=False,
        default=AIEmployeeRoleType.SALES_OPS_ASSISTANT,
    )
    status: Mapped[AIEmployeeStatus] = mapped_column(
        Enum(AIEmployeeStatus, name="ai_employee_status"), nullable=False, default=AIEmployeeStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
