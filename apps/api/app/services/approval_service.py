"""The approval workflow (docs/SECURITY_MODEL.md §5, docs/APPROVAL_WORKFLOW.md):

    AI proposes an action (ApprovalRequest row created, status=pending)
       -> user reviews the request
       -> user approves (optionally with edits), rejects
       -> decision is written to audit_logs
       -> only on approval does anything downstream become eligible to execute

Phase 2 built this loop end to end with no downstream execution. Phase 3 wires
exactly one real-but-simulated action: approving a `send_email_reply` request
calls the mock connector's `send_message` and records the (fake) result here —
never a real send (docs/EMAIL_INTELLIGENCE.md Part 5, founder's explicit "do
not send real emails yet").
"""

import uuid
from datetime import UTC, datetime

from opero_connectors.email_connector import EmailMessageDraft
from opero_connectors.mocks import MockEmailConnector
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval_request import ApprovalRequest, ApprovalStatus
from app.models.audit_log import AuditActorType, AuditLog


class ApprovalAlreadyDecidedError(Exception):
    pass


async def propose_action(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    ai_employee_id: uuid.UUID,
    action_type: str,
    payload: dict,
) -> ApprovalRequest:
    approval = ApprovalRequest(
        organization_id=organization_id,
        ai_employee_id=ai_employee_id,
        action_type=action_type,
        payload=payload,
    )
    db.add(approval)
    await db.flush()

    db.add(
        AuditLog(
            organization_id=organization_id,
            actor_type=AuditActorType.AI_EMPLOYEE,
            actor_id=ai_employee_id,
            action="approval.proposed",
            resource_type="approval_request",
            resource_id=approval.id,
            audit_metadata={"action_type": action_type},
        )
    )
    await db.commit()
    await db.refresh(approval)
    return approval


async def _execute_approved_action(approval: ApprovalRequest, resolved_payload: dict) -> dict | None:
    """Dispatches exactly one real-but-simulated action type. Any other
    `action_type` is a no-op — Phase 3 does not implement unrestricted
    autonomous execution; only the email-reply path is wired, and even that
    only ever calls the mock connector.
    """
    if approval.action_type != "send_email_reply":
        return None

    connector = MockEmailConnector()
    draft = EmailMessageDraft(
        to=resolved_payload.get("to", []),
        subject=resolved_payload.get("subject", ""),
        body_text=resolved_payload.get("body", ""),
    )
    simulated_message_id = await connector.send_message(draft)
    return {"simulated": True, "provider_message_id": simulated_message_id, "sent_to": draft.to}


async def decide(
    db: AsyncSession,
    *,
    approval: ApprovalRequest,
    approve: bool,
    decided_by_user_id: uuid.UUID,
    reason: str | None,
    edited_payload: dict | None = None,
) -> ApprovalRequest:
    if approval.status != ApprovalStatus.PENDING:
        raise ApprovalAlreadyDecidedError(f"Approval request {approval.id} was already {approval.status}.")

    approval.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
    approval.decided_by_user_id = decided_by_user_id
    approval.decision_reason = reason
    approval.decided_at = datetime.now(UTC)

    if approve:
        resolved_payload = edited_payload if edited_payload is not None else dict(approval.payload)
        approval.resolved_payload = resolved_payload

    decision_metadata: dict = {"edited": edited_payload is not None}
    if reason:
        decision_metadata["reason"] = reason

    db.add(
        AuditLog(
            organization_id=approval.organization_id,
            actor_type=AuditActorType.USER,
            actor_id=decided_by_user_id,
            action=f"approval.{approval.status.value}",
            resource_type="approval_request",
            resource_id=approval.id,
            audit_metadata=decision_metadata,
        )
    )

    if approve:
        send_result = await _execute_approved_action(approval, approval.resolved_payload)
        if send_result is not None:
            approval.simulated_send_result = send_result
            db.add(
                AuditLog(
                    organization_id=approval.organization_id,
                    actor_type=AuditActorType.SYSTEM,
                    actor_id=None,
                    action="email.sent",
                    resource_type="approval_request",
                    resource_id=approval.id,
                    audit_metadata=send_result,
                )
            )

    await db.commit()
    await db.refresh(approval)
    return approval
