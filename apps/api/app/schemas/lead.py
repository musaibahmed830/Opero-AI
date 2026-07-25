import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.lead import LeadStatus


class ContactResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    company: str | None

    model_config = {"from_attributes": True}


class LeadResponse(BaseModel):
    id: uuid.UUID
    contact: ContactResponse
    source_thread_id: uuid.UUID | None
    source_message_id: uuid.UUID | None
    status: LeadStatus
    requested_service: str | None
    budget: str | None
    deadline: str | None
    confidence: float | None
    created_at: datetime
    last_activity_at: datetime

    model_config = {"from_attributes": True}


class UpdateLeadStatusRequest(BaseModel):
    status: LeadStatus
