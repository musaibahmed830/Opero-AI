"""OIDC bearer-token verification — a future SSO login path, not wired into any
route yet (docs/SECURITY_MODEL.md §3). Preserved from the original Auth0-first
draft of this codebase: real verification logic, it simply has nothing to
verify against until `auth_issuer`/`auth_audience` are pointed at a live IdP,
which is a deployment-config step, not a code step.
"""

from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import get_settings
from app.core.security import AuthenticatedUser

bearer_scheme = HTTPBearer(auto_error=True)


@lru_cache
def _jwks_client() -> PyJWKClient:
    settings = get_settings()
    jwks_url = settings.auth_issuer.rstrip("/") + "/.well-known/jwks.json"
    return PyJWKClient(jwks_url)


def get_current_user_via_oidc(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthenticatedUser:
    settings = get_settings()
    token = credentials.credentials

    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth_audience,
            issuer=settings.auth_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}"
        ) from exc

    organization_id = claims.get("https://opero.ai/organization_id")
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required organization claim.",
        )

    return AuthenticatedUser(subject=claims["sub"], organization_id=organization_id)
