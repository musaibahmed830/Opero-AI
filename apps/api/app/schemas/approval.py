import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.approval_request import ApprovalStatus


class ProposeActionRequest(BaseModel):
    ai_employee_id: uuid.UUID
    action_type: str
    payload: dict = {}


class DecisionRequest(BaseModel):
    approve: bool
    reason: str | None = None
    edited_payload: dict | None = None


class ApprovalRequestResponse(BaseModel):
    id: uuid.UUID
    ai_employee_id: uuid.UUID
    action_type: str
    payload: dict
    resolved_payload: dict | None
    simulated_send_result: dict | None
    status: ApprovalStatus
    requested_at: datetime
    decided_at: datetime | None
    decided_by_user_id: uuid.UUID | None
    decision_reason: str | None

    model_config = {"from_attributes": True}
