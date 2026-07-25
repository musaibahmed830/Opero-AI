from pydantic import BaseModel, Field

from app.schemas.common import Confidence


class LeadExtractionModelResponse(BaseModel):
    """docs/EMAIL_INTELLIGENCE.md "Lead extraction". Deliberately does NOT ask
    for contact name/email — those come deterministically from the email's
    own sender header (app/services/email_headers.py), not from model
    inference. An earlier version asked the model to echo them back and it
    unreliably omitted them even while correctly extracting everything else —
    asking a model to "extract" a fact you already have is just an extra,
    unreliable hop.

    budget/deadline are left null when the email doesn't explicitly state
    one — the prompt instructs the model not to guess.
    """

    company: str | None = None
    phone: str | None = None
    requested_service: str | None = None
    budget: str | None = Field(default=None, description="Only if an amount is explicitly stated.")
    deadline: str | None = Field(default=None, description="Only if a date/timeframe is explicitly stated.")
    confidence: Confidence
