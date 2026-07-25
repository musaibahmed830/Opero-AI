"""Local email/password session auth — the MVP AuthN mechanism.

Per docs/SECURITY_MODEL.md §3: passwords are hashed with bcrypt (one-way,
never decrypted); a successful login issues a short-lived JWT signed with our
own `session_signing_key`, carrying `sub` (user id) and `organization_id`.

This is deliberately separate from app/core/oidc.py, which validates
externally-issued JWTs for a *future* SSO login path — both terminate in the
same `AuthenticatedUser` shape so route dependencies never need to know which
path authenticated the caller.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext

from app.core.config import get_settings

bearer_scheme = HTTPBearer(auto_error=True)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ALGORITHM = "HS256"
ACCESS_TOKEN_LIFETIME = timedelta(hours=24)


@dataclass(frozen=True)
class AuthenticatedUser:
    subject: str
    organization_id: str


def hash_password(plaintext: str) -> str:
    return _pwd_context.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    return _pwd_context.verify(plaintext, hashed)


def create_access_token(user_id: str, organization_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "organization_id": organization_id,
        "iat": int(now.timestamp()),
        "exp": int((now + ACCESS_TOKEN_LIFETIME).timestamp()),
    }
    return jwt.encode(payload, settings.session_signing_key, algorithm=_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthenticatedUser:
    settings = get_settings()
    try:
        claims = jwt.decode(credentials.credentials, settings.session_signing_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid session token: {exc}"
        ) from exc

    return AuthenticatedUser(subject=claims["sub"], organization_id=claims["organization_id"])
