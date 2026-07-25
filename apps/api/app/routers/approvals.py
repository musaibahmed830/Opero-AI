import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser
from app.models.approval_request import ApprovalRequest
from app.schemas.approval import ApprovalRequestResponse, DecisionRequest, ProposeActionRequest
from app.services.approval_service import ApprovalAlreadyDecidedError, decide, propose_action
from app.services.rbac import require_permission

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED)
async def propose(
    payload: ProposeActionRequest,
    current_user: AuthenticatedUser = Depends(require_permission("approvals.read")),
    db: AsyncSession = Depends(get_db),
) -> ApprovalRequest:
    """Creates a pending approval request.

    Phase 2 has no autonomous orchestrator yet (docs/AI_ARCHITECTURE.md §7), so
    this endpoint stands in for "the AI proposes an action" until Phase 3+
    wires a real orchestrator up to call the same `propose_action` service
    function directly.
    """
    return await propose_action(
        db,
        organization_id=uuid.UUID(current_user.organization_id),
        ai_employee_id=payload.ai_employee_id,
        action_type=payload.action_type,
        payload=payload.payload,
    )


@router.get("", response_model=list[ApprovalRequestResponse])
async def list_approvals(
    current_user: AuthenticatedUser = Depends(require_permission("approvals.read")),
    db: AsyncSession = Depends(get_db),
) -> list[ApprovalRequest]:
    result = await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.organization_id == uuid.UUID(current_user.organization_id))
        .order_by(ApprovalRequest.requested_at.desc())
    )
    return list(result.scalars().all())


async def _get_scoped_approval(
    db: AsyncSession, approval_id: uuid.UUID, organization_id: uuid.UUID
) -> ApprovalRequest:
    result = await db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id, ApprovalRequest.organization_id == organization_id
        )
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found.")
    return approval


@router.get("/{approval_id}", response_model=ApprovalRequestResponse)
async def get_approval(
    approval_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(require_permission("approvals.read")),
    db: AsyncSession = Depends(get_db),
) -> ApprovalRequest:
    return await _get_scoped_approval(db, approval_id, uuid.UUID(current_user.organization_id))


@router.post("/{approval_id}/decide", response_model=ApprovalRequestResponse)
async def decide_approval(
    approval_id: uuid.UUID,
    payload: DecisionRequest,
    current_user: AuthenticatedUser = Depends(require_permission("approvals.decide")),
    db: AsyncSession = Depends(get_db),
) -> ApprovalRequest:
    approval = await _get_scoped_approval(db, approval_id, uuid.UUID(current_user.organization_id))

    try:
        return await decide(
            db,
            approval=approval,
            approve=payload.approve,
            decided_by_user_id=uuid.UUID(current_user.subject),
            reason=payload.reason,
            edited_payload=payload.edited_payload,
        )
    except ApprovalAlreadyDecidedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
