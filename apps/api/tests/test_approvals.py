import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.audit_log import AuditLog


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_and_get_ai_employee(client: AsyncClient) -> tuple[str, str]:
    """Returns (bearer_token, ai_employee_id)."""
    token = (
        await client.post(
            "/v1/auth/register",
            json={
                "organization_name": "Approval Test Co",
                "email": _unique_email(),
                "password": "supersecret123",
            },
        )
    ).json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    employees = (await client.get("/v1/ai-employees", headers=headers)).json()
    return token, employees[0]["id"]


async def test_approval_creation_starts_pending() -> None:
    async with await _client() as client:
        token, ai_employee_id = await _register_and_get_ai_employee(client)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/v1/approvals",
            headers=headers,
            json={
                "ai_employee_id": ai_employee_id,
                "action_type": "send_email",
                "payload": {"to": "a@b.com"},
            },
        )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


async def test_approval_acceptance_updates_status_and_writes_audit_log() -> None:
    async with await _client() as client:
        token, ai_employee_id = await _register_and_get_ai_employee(client)
        headers = {"Authorization": f"Bearer {token}"}

        approval = (
            await client.post(
                "/v1/approvals",
                headers=headers,
                json={"ai_employee_id": ai_employee_id, "action_type": "send_email", "payload": {}},
            )
        ).json()

        decision = await client.post(
            f"/v1/approvals/{approval['id']}/decide",
            headers=headers,
            json={"approve": True, "reason": "looks fine"},
        )

    assert decision.status_code == 200
    body = decision.json()
    assert body["status"] == "approved"
    assert body["decided_at"] is not None
    assert body["decision_reason"] == "looks fine"

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AuditLog).where(AuditLog.resource_id == uuid.UUID(approval["id"]))
        )
        actions = {log.action for log in result.scalars().all()}
    assert actions == {"approval.proposed", "approval.approved"}


async def test_approval_rejection_updates_status_and_writes_audit_log() -> None:
    async with await _client() as client:
        token, ai_employee_id = await _register_and_get_ai_employee(client)
        headers = {"Authorization": f"Bearer {token}"}

        approval = (
            await client.post(
                "/v1/approvals",
                headers=headers,
                json={"ai_employee_id": ai_employee_id, "action_type": "send_email", "payload": {}},
            )
        ).json()

        decision = await client.post(
            f"/v1/approvals/{approval['id']}/decide",
            headers=headers,
            json={"approve": False, "reason": "not yet"},
        )

    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AuditLog).where(
                AuditLog.resource_id == uuid.UUID(approval["id"]), AuditLog.action == "approval.rejected"
            )
        )
        assert result.scalar_one_or_none() is not None


async def test_deciding_an_already_decided_approval_conflicts() -> None:
    async with await _client() as client:
        token, ai_employee_id = await _register_and_get_ai_employee(client)
        headers = {"Authorization": f"Bearer {token}"}

        approval = (
            await client.post(
                "/v1/approvals",
                headers=headers,
                json={"ai_employee_id": ai_employee_id, "action_type": "send_email", "payload": {}},
            )
        ).json()

        first = await client.post(
            f"/v1/approvals/{approval['id']}/decide", headers=headers, json={"approve": True}
        )
        second = await client.post(
            f"/v1/approvals/{approval['id']}/decide", headers=headers, json={"approve": False}
        )

    assert first.status_code == 200
    assert second.status_code == 409


async def test_approval_not_visible_across_organizations() -> None:
    async with await _client() as client:
        token_a, ai_employee_a = await _register_and_get_ai_employee(client)
        token_b, _ = await _register_and_get_ai_employee(client)

        approval = (
            await client.post(
                "/v1/approvals",
                headers={"Authorization": f"Bearer {token_a}"},
                json={"ai_employee_id": ai_employee_a, "action_type": "send_email", "payload": {}},
            )
        ).json()

        cross_org_get = await client.get(
            f"/v1/approvals/{approval['id']}", headers={"Authorization": f"Bearer {token_b}"}
        )

    assert cross_org_get.status_code == 404
