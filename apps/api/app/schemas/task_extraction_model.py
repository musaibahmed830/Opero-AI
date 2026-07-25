from pydantic import BaseModel, Field

from app.models.task import TaskPriority
from app.schemas.common import Confidence


class ExtractedTaskModelItem(BaseModel):
    title: str = Field(max_length=500)
    description: str = ""
    suggested_due_date: str | None = Field(
        default=None, description="Free text (e.g. 'next Tuesday') — only if the email implies one."
    )
    priority: TaskPriority = TaskPriority.NORMAL
    confidence: Confidence


class TaskExtractionModelResponse(BaseModel):
    """A single email can imply zero, one, or several distinct actionable
    tasks (docs/EMAIL_INTELLIGENCE.md "Task extraction") — hence a list rather
    than a single object. An empty list is a valid, common answer.
    """

    tasks: list[ExtractedTaskModelItem] = Field(default_factory=list)
