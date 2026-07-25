import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.email_classification import EmailCategory, EmailPriority, EmailSentiment
from app.schemas.lead import LeadResponse
from app.schemas.task import TaskResponse


class EmailClassificationResponse(BaseModel):
    category: EmailCategory
    priority: EmailPriority
    urgency: EmailPriority
    sentiment: EmailSentiment
    requires_reply: bool
    contains_lead: bool
    contains_task: bool
    contains_deadline: bool
    contains_payment_issue: bool
    possible_spam: bool
    possible_prompt_injection: bool
    confidence: float
    short_summary: str

    model_config = {"from_attributes": True}


class EmailMessageResponse(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    sender: str
    recipients: list[str]
    subject: str
    received_at: datetime
    classification: EmailClassificationResponse | None

    model_config = {"from_attributes": True}


class EmailMessageDetailResponse(EmailMessageResponse):
    body_text: str
    leads: list[LeadResponse] = []
    tasks: list[TaskResponse] = []


class IngestMockEmailsResponse(BaseModel):
    ingested: int


class ProcessEmailResponse(BaseModel):
    status: str = "queued"
