import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.task import Task, TaskStatus
from app.schemas.pagination import PageParams, PaginatedResponse
from app.schemas.task import TaskResponse, UpdateTaskStatusRequest
from app.services.rbac import require_permission

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _get_scoped_task(db: AsyncSession, task_id: uuid.UUID, organization_id: uuid.UUID) -> Task:
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.organization_id == organization_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task


@router.get("", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    current_user: AuthenticatedUser = Depends(require_permission("tasks.read")),
    db: AsyncSession = Depends(get_db),
    pagination: PageParams = Depends(),
) -> PaginatedResponse:
    conditions = [Task.organization_id == uuid.UUID(current_user.organization_id)]
    if status_filter is not None:
        conditions.append(Task.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(Task).where(*conditions))).scalar_one()
    result = await db.execute(
        select(Task)
        .where(*conditions)
        .order_by(Task.created_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    tasks = list(result.scalars().all())

    return PaginatedResponse(
        items=[TaskResponse.model_validate(task) for task in tasks],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_permission("tasks.read")),
    db: AsyncSession = Depends(get_db),
) -> Task:
    return await _get_scoped_task(db, task_id, uuid.UUID(current_user.organization_id))


@router.post("/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: uuid.UUID,
    payload: UpdateTaskStatusRequest,
    current_user: AuthenticatedUser = Depends(require_permission("tasks.write")),
    db: AsyncSession = Depends(get_db),
) -> Task:
    task = await _get_scoped_task(db, task_id, uuid.UUID(current_user.organization_id))
    task.status = payload.status
    await db.commit()
    await db.refresh(task)
    return task
