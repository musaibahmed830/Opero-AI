"""Signed, short-lived state tokens for the Gmail OAuth redirect round-trip.

Google's callback hits our server directly (no Authorization header), so we
can't rely on the usual Bearer-token auth to know which organization/user
initiated the connection. Binding organization/user into a signed `state`
param — verified on callback — is what prevents a forged callback from
attaching a mailbox to the wrong organization.
"""

import time

import jwt

from app.core.config import get_settings

_ALGORITHM = "HS256"


def create_state(organization_id: str, user_id: str) -> str:
    settings = get_settings()
    payload = {"organization_id": organization_id, "user_id": user_id, "iat": int(time.time())}
    return jwt.encode(payload, settings.oauth_state_secret, algorithm=_ALGORITHM)


def verify_state(token: str, max_age_seconds: int = 600) -> dict[str, str]:
    settings = get_settings()
    payload = jwt.decode(token, settings.oauth_state_secret, algorithms=[_ALGORITHM])
    if time.time() - payload["iat"] > max_age_seconds:
        raise jwt.ExpiredSignatureError("OAuth state token expired")
    return payload
