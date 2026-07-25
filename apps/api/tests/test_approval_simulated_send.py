import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.audit_log import AuditLog
from tests.factories import auth_headers, client, register


async def _register_and_get_ai_employee(client, organization_name: str = "Send Test Co"):
    token = await register(client, organization_name)
    headers = auth_headers(token)
    employees = (await client.get("/v1/ai-employees", headers=headers)).json()
    return token, employees[0]["id"]


async def test_approving_send_email_reply_dispatches_simulated_send() -> None:
    async with client() as c:
        token, ai_employee_id = await _register_and_get_ai_employee(c)
        headers = auth_headers(token)

        approval = (
            await c.post(
                "/v1/approvals",
                headers=headers,
                json={
                    "ai_employee_id": ai_employee_id,
                    "action_type": "send_email_reply",
                    "payload": {"to": ["prospect@example.com"], "subject": "Re: Quote", "body": "Hi there."},
                },
            )
        ).json()

        decision = await c.post(
            f"/v1/approvals/{approval['id']}/decide", headers=headers, json={"approve": True}
        )

    assert decision.status_code == 200
    body = decision.json()
    assert body["resolved_payload"] == approval["payload"]
    assert body["simulated_send_result"]["simulated"] is True
    assert body["simulated_send_result"]["sent_to"] == ["prospect@example.com"]

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AuditLog).where(AuditLog.resource_id == uuid.UUID(approval["id"]))
        )
        actions = {log.action for log in result.scalars().all()}
    assert "email.sent" in actions


async def test_approving_with_edited_payload_sends_the_edit_not_the_original() -> None:
    async with client() as c:
        token, ai_employee_id = await _register_and_get_ai_employee(c)
        headers = auth_headers(token)

        approval = (
            await c.post(
                "/v1/approvals",
                headers=headers,
                json={
                    "ai_employee_id": ai_employee_id,
                    "action_type": "send_email_reply",
                    "payload": {"to": ["prospect@example.com"], "subject": "Draft", "body": "Original."},
                },
            )
        ).json()

        edited = {"to": ["prospect@example.com"], "subject": "Edited subject", "body": "Edited body."}
        decision = await c.post(
            f"/v1/approvals/{approval['id']}/decide",
            headers=headers,
            json={"approve": True, "edited_payload": edited},
        )

    assert decision.status_code == 200
    body = decision.json()
    assert body["resolved_payload"] == edited
    assert body["payload"]["body"] == "Original."  # the original AI proposal is never mutated


async def test_rejecting_send_email_reply_never_dispatches_a_send() -> None:
    async with client() as c:
        token, ai_employee_id = await _register_and_get_ai_employee(c)
        headers = auth_headers(token)

        approval = (
            await c.post(
                "/v1/approvals",
                headers=headers,
                json={
                    "ai_employee_id": ai_employee_id,
                    "action_type": "send_email_reply",
                    "payload": {"to": ["prospect@example.com"], "subject": "Draft", "body": "Body."},
                },
            )
        ).json()

        decision = await c.post(
            f"/v1/approvals/{approval['id']}/decide", headers=headers, json={"approve": False}
        )

    assert decision.status_code == 200
    assert decision.json()["simulated_send_result"] is None


async def test_unrecognized_action_type_is_a_no_op_on_approval() -> None:
    """No unrestricted autonomous execution: only send_email_reply is wired to
    do anything on approval; any other action_type is approved but nothing
    downstream executes.
    """
    async with client() as c:
        token, ai_employee_id = await _register_and_get_ai_employee(c)
        headers = auth_headers(token)

        approval = (
            await c.post(
                "/v1/approvals",
                headers=headers,
                json={"ai_employee_id": ai_employee_id, "action_type": "delete_account", "payload": {}},
            )
        ).json()

        decision = await c.post(
            f"/v1/approvals/{approval['id']}/decide", headers=headers, json={"approve": True}
        )

    assert decision.status_code == 200
    assert decision.json()["simulated_send_result"] is None
