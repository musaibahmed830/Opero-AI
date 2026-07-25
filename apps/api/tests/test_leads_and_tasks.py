import uuid

import jwt

from app.core.database import AsyncSessionLocal
from app.models.contact import Contact
from app.models.lead import Lead, LeadStatus
from app.models.task import Task, TaskCategory, TaskPriority
from tests.factories import auth_headers, client, register


def _decode_org(token: str) -> uuid.UUID:
    return uuid.UUID(jwt.decode(token, options={"verify_signature": False})["organization_id"])


async def _seed_lead(organization_id: uuid.UUID) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        contact = Contact(
            organization_id=organization_id,
            name="Jordan Rivers",
            email=f"jordan-{uuid.uuid4().hex[:8]}@example.com",
        )
        db.add(contact)
        await db.flush()

        lead = Lead(
            organization_id=organization_id,
            contact_id=contact.id,
            status=LeadStatus.NEW,
            requested_service="Website redesign",
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        return lead.id


async def _seed_task(organization_id: uuid.UUID) -> uuid.UUID:
    async with AsyncSessionLocal() as db:
        task = Task(
            organization_id=organization_id,
            title="Follow up with prospect",
            category=TaskCategory.FOLLOW_UP,
            priority=TaskPriority.NORMAL,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task.id


async def test_lead_list_get_and_status_update() -> None:
    async with client() as c:
        token = await register(c)
        headers = auth_headers(token)
        lead_id = await _seed_lead(_decode_org(token))

        listed = await c.get("/v1/leads", headers=headers)
        detail = await c.get(f"/v1/leads/{lead_id}", headers=headers)
        updated = await c.post(f"/v1/leads/{lead_id}/status", headers=headers, json={"status": "won"})

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["contact"]["name"] == "Jordan Rivers"
    assert updated.status_code == 200
    assert updated.json()["status"] == "won"


async def test_lead_not_visible_across_organizations() -> None:
    async with client() as c:
        token_a = await register(c, "Lead Org A")
        token_b = await register(c, "Lead Org B")
        lead_id = await _seed_lead(_decode_org(token_a))

        cross_org = await c.get(f"/v1/leads/{lead_id}", headers=auth_headers(token_b))

    assert cross_org.status_code == 404


async def test_task_list_get_and_status_update() -> None:
    async with client() as c:
        token = await register(c)
        headers = auth_headers(token)
        task_id = await _seed_task(_decode_org(token))

        listed = await c.get("/v1/tasks", headers=headers)
        detail = await c.get(f"/v1/tasks/{task_id}", headers=headers)
        updated = await c.post(f"/v1/tasks/{task_id}/status", headers=headers, json={"status": "done"})

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["status"] == "done"


async def test_task_not_visible_across_organizations() -> None:
    async with client() as c:
        token_a = await register(c, "Task Org A")
        token_b = await register(c, "Task Org B")
        task_id = await _seed_task(_decode_org(token_a))

        cross_org = await c.get(f"/v1/tasks/{task_id}", headers=auth_headers(token_b))

    assert cross_org.status_code == 404


async def test_task_status_filter() -> None:
    async with client() as c:
        token = await register(c)
        organization_id = _decode_org(token)
        headers = auth_headers(token)

        open_task_id = await _seed_task(organization_id)
        done_task_id = await _seed_task(organization_id)
        await c.post(f"/v1/tasks/{done_task_id}/status", headers=headers, json={"status": "done"})

        open_only = await c.get("/v1/tasks?status=open", headers=headers)

    assert open_only.status_code == 200
    ids = {item["id"] for item in open_only.json()["items"]}
    assert str(open_task_id) in ids
    assert str(done_task_id) not in ids
