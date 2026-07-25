import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.daily_report import DailyReport
from app.schemas.pagination import PageParams, PaginatedResponse
from app.schemas.report import DailyReportResponse, GenerateReportRequest
from app.services.daily_report import generate_daily_report
from app.services.rbac import require_permission

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate", response_model=DailyReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_report(
    payload: GenerateReportRequest,
    current_user: AuthenticatedUser = Depends(require_permission("reports.generate")),
    db: AsyncSession = Depends(get_db),
) -> DailyReport:
    """Generates (or returns the existing) report for a date, defaulting to
    today. Idempotent per (organization, report_date) — a report is
    generated once and is read-only after that (docs/DAILY_REPORT_ENGINE.md).
    """
    return await generate_daily_report(
        db, organization_id=uuid.UUID(current_user.organization_id), report_date=payload.report_date
    )


@router.get("", response_model=PaginatedResponse[DailyReportResponse])
async def list_reports(
    current_user: AuthenticatedUser = Depends(require_permission("reports.read")),
    db: AsyncSession = Depends(get_db),
    pagination: PageParams = Depends(),
) -> PaginatedResponse:
    organization_id = uuid.UUID(current_user.organization_id)
    total = (
        await db.execute(
            select(func.count())
            .select_from(DailyReport)
            .where(DailyReport.organization_id == organization_id)
        )
    ).scalar_one()
    result = await db.execute(
        select(DailyReport)
        .where(DailyReport.organization_id == organization_id)
        .order_by(DailyReport.report_date.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    reports = list(result.scalars().all())

    return PaginatedResponse(
        items=[DailyReportResponse.model_validate(r) for r in reports],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{report_date}", response_model=DailyReportResponse)
async def get_report(
    report_date: date,
    current_user: AuthenticatedUser = Depends(require_permission("reports.read")),
    db: AsyncSession = Depends(get_db),
) -> DailyReport:
    result = await db.execute(
        select(DailyReport).where(
            DailyReport.organization_id == uuid.UUID(current_user.organization_id),
            DailyReport.report_date == report_date,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No report found for that date.")
    return report
