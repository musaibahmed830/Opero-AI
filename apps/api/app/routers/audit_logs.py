import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogResponse
from app.services.rbac import require_permission

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    current_user: AuthenticatedUser = Depends(require_permission("audit.read")),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == uuid.UUID(current_user.organization_id))
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    )
    return list(result.scalars().all())
