"""Full email intelligence pipeline orchestration (docs/EMAIL_INTELLIGENCE.md
"Pipeline overview"):

    email ingested -> classified -> lead/task extraction (if flagged)
       -> reply draft generated (if a reply is warranted)
       -> approval request proposed (never sent directly)

Each stage's service function already validates and commits its own output
independently, so a failure partway through (e.g. the model errors on draft
generation) still leaves the classification and any extracted lead/task
persisted rather than losing everything.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_employee import AIEmployee
from app.models.email_classification import EmailClassification
from app.models.email_message import EmailMessage
from app.services.approval_service import propose_action
from app.services.draft_generation import generate_reply_draft
from app.services.email_classification import classify_email
from app.services.email_headers import parse_sender
from app.services.lead_extraction import extract_lead
from app.services.task_extraction import extract_tasks


async def process_email(
    db: AsyncSession, *, message: EmailMessage, organization_id: uuid.UUID
) -> EmailClassification:
    classification = await classify_email(db, message=message, organization_id=organization_id)

    if classification.contains_lead:
        await extract_lead(db, message=message, organization_id=organization_id)

    if classification.contains_task:
        await extract_tasks(db, message=message, organization_id=organization_id)

    if classification.requires_reply:
        await _propose_reply(db, message=message, organization_id=organization_id)

    return classification


async def _propose_reply(db: AsyncSession, *, message: EmailMessage, organization_id: uuid.UUID) -> None:
    ai_employee_result = await db.execute(
        select(AIEmployee).where(AIEmployee.organization_id == organization_id)
    )
    ai_employee = ai_employee_result.scalars().first()
    if ai_employee is None:
        # Every organization gets one AI employee at signup (app/services/
        # auth_service.py); this only trips for orgs created outside that path
        # (e.g. ad-hoc test fixtures), so skip rather than invent one here.
        return

    draft = await generate_reply_draft(db, message=message, organization_id=organization_id)
    _, sender_email = parse_sender(message.sender)

    await propose_action(
        db,
        organization_id=organization_id,
        ai_employee_id=ai_employee.id,
        action_type="send_email_reply",
        payload={
            "to": [sender_email],
            "subject": draft.subject,
            "body": draft.body,
            "tone": draft.tone,
            "referenced_knowledge": draft.referenced_knowledge,
            "confidence": draft.confidence,
            "missing_information": draft.missing_information,
            "warnings": draft.warnings,
            "sensitive_flags": draft.sensitive_flags,
            "trace_id": str(draft.trace_id),
            "source_message_id": str(message.id),
        },
    )
