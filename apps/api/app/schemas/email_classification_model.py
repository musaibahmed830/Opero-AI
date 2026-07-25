from pydantic import BaseModel, Field

from app.models.email_classification import EmailCategory, EmailPriority, EmailSentiment
from app.schemas.common import Confidence


class EmailClassificationModelResponse(BaseModel):
    """The model's structured output — validated before anything downstream
    trusts it (docs/SECURITY_MODEL.md §16). Deliberately excludes
    `possible_prompt_injection`: that flag is computed independently by
    `app.services.prompt_injection` against the raw email body, never
    self-reported by the same model an injection attempt is trying to
    manipulate (docs/PROMPT_INJECTION_DEFENCE.md).
    """

    category: EmailCategory
    priority: EmailPriority
    urgency: EmailPriority = Field(description="Time-sensitivity, independent of importance (priority).")
    sentiment: EmailSentiment
    requires_reply: bool
    contains_lead: bool
    contains_task: bool
    contains_deadline: bool
    contains_payment_issue: bool
    possible_spam: bool
    confidence: Confidence
    short_summary: str
