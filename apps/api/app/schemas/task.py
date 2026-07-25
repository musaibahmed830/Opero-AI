import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.task import TaskCategory, TaskPriority, TaskStatus


class TaskResponse(BaseModel):
    id: uuid.UUID
    source_thread_id: uuid.UUID | None
    source_message_id: uuid.UUID | None
    title: str
    description: str
    category: TaskCategory
    priority: TaskPriority
    status: TaskStatus
    confidence: float | None
    due_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateTaskStatusRequest(BaseModel):
    status: TaskStatus
