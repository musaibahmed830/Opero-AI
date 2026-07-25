"""Shared test helpers — not collected by pytest (no test_ prefix)."""

import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app


def unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def register(client: AsyncClient, organization_name: str = "Test Co") -> str:
    """Returns a bearer token for a freshly registered organization + owner user."""
    response = await client.post(
        "/v1/auth/register",
        json={
            "organization_name": organization_name,
            "email": unique_email(),
            "password": "supersecret123",
        },
    )
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
