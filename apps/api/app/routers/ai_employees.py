import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.models.ai_employee import AIEmployee
from app.schemas.ai_employee import AIEmployeeResponse

router = APIRouter(prefix="/ai-employees", tags=["ai-employees"])


@router.get("", response_model=list[AIEmployeeResponse])
async def list_ai_employees(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AIEmployee]:
    result = await db.execute(
        select(AIEmployee).where(AIEmployee.organization_id == uuid.UUID(current_user.organization_id))
    )
    return list(result.scalars().all())
