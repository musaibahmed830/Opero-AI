"""Seeds a fictional demo organization end-to-end (docs/LOCAL_DEMO_GUIDE.md):

    org + owner user -> sample knowledge documents (ingested + embedded) ->
    12 mock inbox emails -> full pipeline (classify/extract/draft/propose)
    for each -> today's daily report

Everything here goes through the same service functions the API uses — this
script is a convenience wrapper, not a separate code path, so what you see
running `make demo-seed` is exactly what the product actually does. Calls the
real Ollama model for classification/extraction/drafting/embeddings/narrative,
so it takes a few minutes and requires the model stack to be up.

Usage: python scripts/seed_demo_org.py
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.email_message import EmailMessage  # noqa: E402
from app.models.email_thread import EmailThread  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import register_organization_and_owner  # noqa: E402
from app.services.daily_report import generate_daily_report  # noqa: E402
from app.services.document_ingestion import create_document, process_document  # noqa: E402
from app.services.email_ingestion import ingest_mock_emails  # noqa: E402
from app.services.email_processing import process_email  # noqa: E402

DEMO_ORG_NAME = "Opero Demo Co"
DEMO_OWNER_EMAIL = "demo@opero.ai"
DEMO_OWNER_PASSWORD = "DemoPass123!"

# Fictional company knowledge — the same kind of small-business documents the
# founder's spec describes (refund policy, service catalog, support hours).
# No real company's data.
_DEMO_DOCUMENTS = {
    "refund_policy.txt": (
        "Opero Demo Co Refund Policy\n\n"
        "Customers may request a full refund within 30 days of purchase for any service package, "
        "provided no more than 20% of the contracted work has been delivered. Refund requests must be "
        "submitted in writing to billing@operodemo.example. Approved refunds are processed within 5 "
        "business days back to the original payment method. Custom / bespoke development work is "
        "non-refundable once development has started."
    ),
    "service_catalog.txt": (
        "Opero Demo Co Service Catalog\n\n"
        "Starter Website Package: $1,500, includes up to 5 pages, delivered in 2-3 weeks.\n"
        "Growth Website Package: $4,000, includes up to 15 pages, a blog, and basic SEO setup, "
        "delivered in 4-6 weeks.\n"
        "Custom Web Application: quoted individually after a scoping call, typical range $10,000-$40,000.\n"
        "Monthly Care Plan: $150/month, includes hosting, security updates, and up to 2 hours of "
        "content changes."
    ),
    "support_hours.txt": (
        "Opero Demo Co Support Hours\n\n"
        "Our support team is available Monday through Friday, 9am to 5pm Eastern Time, excluding "
        "public holidays. Support requests submitted outside these hours are answered the next "
        "business day. Critical production outages for Growth and Custom clients are covered by a "
        "best-effort on-call rotation."
    ),
}


async def _get_or_create_demo_org() -> tuple[str, str]:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == DEMO_OWNER_EMAIL))
        user = existing.scalar_one_or_none()
        if user is not None:
            print(f"Demo organization already exists ({user.organization_id}); reusing it.")
            return str(user.organization_id), DEMO_OWNER_EMAIL

        organization, user = await register_organization_and_owner(
            db,
            organization_name=DEMO_ORG_NAME,
            email=DEMO_OWNER_EMAIL,
            password=DEMO_OWNER_PASSWORD,
        )
        print(f"Created demo organization '{organization.name}' ({organization.id})")
        return str(organization.id), DEMO_OWNER_EMAIL


async def _seed_knowledge(organization_id: str, uploaded_by: str) -> None:
    org_uuid = uuid.UUID(organization_id)
    user_uuid = uuid.UUID(uploaded_by)

    for filename, content in _DEMO_DOCUMENTS.items():
        async with AsyncSessionLocal() as db:
            try:
                document = await create_document(
                    db,
                    organization_id=org_uuid,
                    uploaded_by=user_uuid,
                    original_filename=filename,
                    content=content.encode(),
                    content_type="text/plain",
                )
            except Exception as exc:  # DuplicateDocumentError on re-run
                print(f"  skipping {filename}: {exc}")
                continue

        async with AsyncSessionLocal() as db:
            document = await db.get(Document, document.id)
            await process_document(db, document)
        print(f"  ingested + processed {filename}")


async def _seed_emails_and_run_pipeline(organization_id: str) -> None:
    org_uuid = uuid.UUID(organization_id)

    async with AsyncSessionLocal() as db:
        ingested = await ingest_mock_emails(db, org_uuid)
        print(f"  ingested {ingested} mock emails")

        thread_ids = (
            (await db.execute(select(EmailThread.id).where(EmailThread.organization_id == org_uuid)))
            .scalars()
            .all()
        )
        messages = (
            (await db.execute(select(EmailMessage).where(EmailMessage.thread_id.in_(thread_ids))))
            .scalars()
            .all()
        )

    for i, message in enumerate(messages, start=1):
        async with AsyncSessionLocal() as db:
            message = await db.get(EmailMessage, message.id)
            classification = await process_email(db, message=message, organization_id=org_uuid)
        print(
            f"  [{i}/{len(messages)}] classified '{message.subject[:50]}' as "
            f"{classification.category.value}/{classification.priority.value}"
        )


async def _seed_report(organization_id: str) -> None:
    async with AsyncSessionLocal() as db:
        report = await generate_daily_report(
            db, organization_id=uuid.UUID(organization_id), report_date=datetime.now(UTC).date()
        )
    print(f"  generated report for {report.report_date}: {report.emails_handled} emails handled")


async def main() -> None:
    print("Seeding demo organization...")
    organization_id, owner_email = await _get_or_create_demo_org()

    async with AsyncSessionLocal() as db:
        owner = (await db.execute(select(User).where(User.email == owner_email))).scalar_one()
        owner_id = str(owner.id)
        org_name = (
            await db.execute(select(Organization.name).where(Organization.id == owner.organization_id))
        ).scalar_one()

    print(f"Organization: {org_name} ({organization_id})")
    print(f"Login: {owner_email} / {DEMO_OWNER_PASSWORD}")

    print("Seeding knowledge base...")
    await _seed_knowledge(organization_id, owner_id)

    print("Seeding inbox and running the classification/extraction/drafting pipeline...")
    await _seed_emails_and_run_pipeline(organization_id)

    print("Generating today's daily report...")
    await _seed_report(organization_id)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
