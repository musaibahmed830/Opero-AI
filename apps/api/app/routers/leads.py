import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.lead import Lead, LeadStatus
from app.schemas.lead import LeadResponse, UpdateLeadStatusRequest
from app.schemas.pagination import PageParams, PaginatedResponse
from app.services.rbac import require_permission

router = APIRouter(prefix="/leads", tags=["leads"])


async def _get_scoped_lead(db: AsyncSession, lead_id: uuid.UUID, organization_id: uuid.UUID) -> Lead:
    result = await db.execute(
        select(Lead)
        .options(selectinload(Lead.contact))
        .where(Lead.id == lead_id, Lead.organization_id == organization_id)
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")
    return lead


@router.get("", response_model=PaginatedResponse[LeadResponse])
async def list_leads(
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    current_user: AuthenticatedUser = Depends(require_permission("leads.read")),
    db: AsyncSession = Depends(get_db),
    pagination: PageParams = Depends(),
) -> PaginatedResponse:
    conditions = [Lead.organization_id == uuid.UUID(current_user.organization_id)]
    if status_filter is not None:
        conditions.append(Lead.status == status_filter)

    total = (await db.execute(select(func.count()).select_from(Lead).where(*conditions))).scalar_one()
    result = await db.execute(
        select(Lead)
        .options(selectinload(Lead.contact))
        .where(*conditions)
        .order_by(Lead.last_activity_at.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    leads = list(result.scalars().all())

    return PaginatedResponse(
        items=[LeadResponse.model_validate(lead) for lead in leads],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_permission("leads.read")),
    db: AsyncSession = Depends(get_db),
) -> Lead:
    return await _get_scoped_lead(db, lead_id, uuid.UUID(current_user.organization_id))


@router.post("/{lead_id}/status", response_model=LeadResponse)
async def update_lead_status(
    lead_id: uuid.UUID,
    payload: UpdateLeadStatusRequest,
    current_user: AuthenticatedUser = Depends(require_permission("leads.write")),
    db: AsyncSession = Depends(get_db),
) -> Lead:
    lead = await _get_scoped_lead(db, lead_id, uuid.UUID(current_user.organization_id))
    lead.status = payload.status
    await db.commit()
    await db.refresh(lead, attribute_names=["contact"])
    return lead
