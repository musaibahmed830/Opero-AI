import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.audit_log import AuditActorType


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_type: AuditActorType
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    audit_metadata: dict
    created_at: datetime

    model_config = {"from_attributes": True}
