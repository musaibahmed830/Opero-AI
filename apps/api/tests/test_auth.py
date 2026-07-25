import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password, verify_password
from app.main import app
from app.models.user import User


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_password_is_hashed_not_stored_plaintext() -> None:
    hashed = hash_password("correct-horse-battery-staple")

    assert hashed != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", hashed) is True
    assert verify_password("wrong-password", hashed) is False


async def test_register_creates_organization_and_owner_user() -> None:
    email = _unique_email()
    async with await _client() as client:
        response = await client.post(
            "/v1/auth/register",
            json={"organization_name": "Test Co", "email": email, "password": "supersecret123"},
        )

    assert response.status_code == 201
    assert "access_token" in response.json()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        assert user.hashed_password is not None
        assert user.hashed_password != "supersecret123"


async def test_register_rejects_duplicate_email() -> None:
    email = _unique_email()
    payload = {"organization_name": "Test Co", "email": email, "password": "supersecret123"}

    async with await _client() as client:
        first = await client.post("/v1/auth/register", json=payload)
        second = await client.post("/v1/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


async def test_login_succeeds_with_correct_password_and_fails_with_wrong_one() -> None:
    email = _unique_email()
    async with await _client() as client:
        await client.post(
            "/v1/auth/register",
            json={"organization_name": "Test Co", "email": email, "password": "correct-password-123"},
        )

        good = await client.post("/v1/auth/login", json={"email": email, "password": "correct-password-123"})
        bad = await client.post("/v1/auth/login", json={"email": email, "password": "wrong-password"})

    assert good.status_code == 200
    assert "access_token" in good.json()
    assert bad.status_code == 401


async def test_me_returns_current_authenticated_user() -> None:
    email = _unique_email()
    async with await _client() as client:
        register_response = await client.post(
            "/v1/auth/register",
            json={"organization_name": "Test Co", "email": email, "password": "supersecret123"},
        )
        token = register_response.json()["access_token"]

        me_response = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me_response.status_code == 200
    assert me_response.json()["email"] == email


async def test_organization_data_is_isolated_between_organizations() -> None:
    """A user's token only ever reveals their own organization's data — never
    another organization's, even when both exist in the same database
    (docs/SECURITY_MODEL.md §4).
    """
    email_a = _unique_email()
    email_b = _unique_email()

    async with await _client() as client:
        token_a = (
            await client.post(
                "/v1/auth/register",
                json={"organization_name": "Org A", "email": email_a, "password": "supersecret123"},
            )
        ).json()["access_token"]
        token_b = (
            await client.post(
                "/v1/auth/register",
                json={"organization_name": "Org B", "email": email_b, "password": "supersecret123"},
            )
        ).json()["access_token"]

        accounts_a = await client.get(
            "/v1/integrations/gmail/accounts", headers={"Authorization": f"Bearer {token_a}"}
        )
        me_b = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})

    assert accounts_a.status_code == 200
    assert accounts_a.json() == []  # org A has no email accounts connected, and never sees org B's
    assert me_b.json()["email"] == email_b
