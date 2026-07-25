import pytest

from tests.factories import auth_headers, client, register

# Every report-generation call also asks the live model to write a narrative
# on top of the (already deterministic) metrics — there's no zero-model-call
# path here the way RAG's insufficient_evidence short-circuit has one, so
# every test in this module is a live_model test (docs/TESTING_GUIDE.md).
pytestmark = pytest.mark.live_model


async def test_generate_report_with_no_activity_has_zero_metrics() -> None:
    async with client() as c:
        token = await register(c)
        headers = auth_headers(token)

        response = await c.post("/v1/reports/generate", headers=headers, json={"report_date": "2020-01-01"})

    assert response.status_code == 201
    body = response.json()
    assert body["emails_handled"] == 0
    assert body["leads_created"] == 0
    assert body["follow_ups_overdue"] == 0
    assert body["metrics"]["emails_by_category"] == {}
    assert body["metrics"]["approvals_pending"] == 0


async def test_generating_the_same_day_twice_is_idempotent() -> None:
    async with client() as c:
        token = await register(c)
        headers = auth_headers(token)

        first = await c.post("/v1/reports/generate", headers=headers, json={"report_date": "2020-02-02"})
        second = await c.post("/v1/reports/generate", headers=headers, json={"report_date": "2020-02-02"})

    assert first.json()["id"] == second.json()["id"]


async def test_report_not_visible_across_organizations() -> None:
    async with client() as c:
        token_a = await register(c, "Report Org A")
        token_b = await register(c, "Report Org B")

        await c.post(
            "/v1/reports/generate", headers=auth_headers(token_a), json={"report_date": "2020-03-03"}
        )

        cross_org = await c.get("/v1/reports/2020-03-03", headers=auth_headers(token_b))
        own_org = await c.get("/v1/reports/2020-03-03", headers=auth_headers(token_a))

    assert cross_org.status_code == 404
    assert own_org.status_code == 200


async def test_get_report_for_date_with_no_report_returns_404() -> None:
    async with client() as c:
        token = await register(c)
        response = await c.get("/v1/reports/2099-12-31", headers=auth_headers(token))

    assert response.status_code == 404


async def test_report_narrative_is_generated_from_real_model() -> None:
    async with client() as c:
        token = await register(c)
        headers = auth_headers(token)
        await c.post("/v1/emails/ingest-mock", headers=headers)

        response = await c.post(
            "/v1/reports/generate", headers=headers, json={"report_date": "2020-04-04"}
        )

    assert response.status_code == 201
    assert len(response.json()["narrative"]) > 0
