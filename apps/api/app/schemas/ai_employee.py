import uuid

from pydantic import BaseModel

from app.models.ai_employee import AIEmployeeRoleType, AIEmployeeStatus


class AIEmployeeResponse(BaseModel):
    id: uuid.UUID
    name: str
    role_type: AIEmployeeRoleType
    status: AIEmployeeStatus

    model_config = {"from_attributes": True}
