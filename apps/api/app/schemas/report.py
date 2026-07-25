import uuid
from datetime import date, datetime

from pydantic import BaseModel


class DailyReportResponse(BaseModel):
    id: uuid.UUID
    report_date: date
    emails_handled: int
    drafts_pending: int
    leads_created: int
    follow_ups_overdue: int
    tasks_completed: int
    metrics: dict
    narrative: str
    generated_at: datetime

    model_config = {"from_attributes": True}


class GenerateReportRequest(BaseModel):
    report_date: date | None = None
