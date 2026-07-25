"""Gmail REST client — plain httpx calls against Google's OAuth2 and Gmail APIs.

Deliberately avoids google-api-python-client/google-auth-oauthlib: this app is
async end-to-end (see app/services/model_router.py for the same pattern), and
those libraries are synchronous. Gmail's REST surface is plain HTTP + JSON, so
a full SDK buys nothing here.
"""

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
]


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: float  # unix epoch seconds


class GmailOAuthClient:
    """Handles the OAuth2 authorization-code exchange — nothing account-specific."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self._settings.google_oauth_client_id,
            "redirect_uri": self._settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> TokenSet:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self._settings.google_oauth_client_id,
                    "client_secret": self._settings.google_oauth_client_secret,
                    "redirect_uri": self._settings.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            data = response.json()

        return TokenSet(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=time.time() + data["expires_in"],
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenSet:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": refresh_token,
                    "client_id": self._settings.google_oauth_client_id,
                    "client_secret": self._settings.google_oauth_client_secret,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()

        return TokenSet(
            access_token=data["access_token"],
            refresh_token=refresh_token,  # Google doesn't reissue this on refresh.
            expires_at=time.time() + data["expires_in"],
        )


class GmailAPIClient:
    """Per-account Gmail REST calls. Takes a valid (unexpired) access token."""

    def __init__(self, access_token: str) -> None:
        self._access_token = access_token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(
            base_url=GMAIL_API_BASE,
            headers={"Authorization": f"Bearer {self._access_token}"},
            timeout=30.0,
        ) as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def get_profile(self) -> dict[str, Any]:
        return await self._get("/users/me/profile")

    async def list_message_ids(self, max_results: int = 20) -> list[str]:
        data = await self._get("/users/me/messages", params={"maxResults": max_results})
        return [m["id"] for m in data.get("messages", [])]

    async def get_message(self, message_id: str) -> dict[str, Any]:
        return await self._get(f"/users/me/messages/{message_id}", params={"format": "full"})

    async def list_history(self, start_history_id: str) -> dict[str, Any]:
        return await self._get(
            "/users/me/history",
            params={"startHistoryId": start_history_id, "historyTypes": "messageAdded"},
        )
