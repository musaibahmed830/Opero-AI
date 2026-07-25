import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.database import get_db
from app.core.oauth_state import create_state, verify_state
from app.core.security import AuthenticatedUser, get_current_user
from app.models.email_account import EmailAccount
from app.models.integration import Integration, IntegrationProvider
from app.schemas.gmail import (
    CallbackResponse,
    ConnectResponse,
    EmailAccountResponse,
    SyncResponse,
)
from app.services.gmail_client import GmailAPIClient, GmailOAuthClient
from app.services.gmail_sync import sync_account

router = APIRouter(prefix="/integrations/gmail", tags=["gmail"])


@router.get("/connect", response_model=ConnectResponse)
async def connect(current_user: AuthenticatedUser = Depends(get_current_user)) -> ConnectResponse:
    """Returns the Google consent-screen URL for the caller's dashboard to navigate to.

    Kept as a JSON response (rather than an HTTP redirect) so the request can
    still carry the normal Bearer auth header; the dashboard does the actual
    `window.location` navigation client-side.
    """
    state = create_state(organization_id=current_user.organization_id, user_id=current_user.subject)
    oauth_client = GmailOAuthClient()
    return ConnectResponse(authorization_url=oauth_client.build_authorization_url(state))


@router.get("/callback", response_model=CallbackResponse)
async def callback(code: str, state: str, db: AsyncSession = Depends(get_db)) -> CallbackResponse:
    """Google redirects here after the user grants (or denies) consent."""
    try:
        claims = verify_state(state)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid or expired OAuth state: {exc}"
        ) from exc

    oauth_client = GmailOAuthClient()
    tokens = await oauth_client.exchange_code(code)
    if tokens.refresh_token is None:
        # Google omits this if the user has already granted consent before without
        # `prompt=consent` forcing re-issuance — build_authorization_url always sets
        # prompt=consent, so this should not happen in practice.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google did not return a refresh token; reconnect the account.",
        )

    profile = await GmailAPIClient(tokens.access_token).get_profile()
    email_address = profile["emailAddress"]
    organization_id = uuid.UUID(claims["organization_id"])

    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.organization_id == organization_id,
            EmailAccount.email_address == email_address,
        )
    )
    account = result.scalar_one_or_none()

    if account is None:
        integration = Integration(organization_id=organization_id, provider=IntegrationProvider.GMAIL)
        db.add(integration)
        await db.flush()

        account = EmailAccount(
            organization_id=organization_id,
            integration_id=integration.id,
            email_address=email_address,
            refresh_token_encrypted=encrypt_secret(tokens.refresh_token),
        )
        db.add(account)
    else:
        account.refresh_token_encrypted = encrypt_secret(tokens.refresh_token)

    await db.commit()
    return CallbackResponse(connected=True, email_address=email_address)


@router.get("/accounts", response_model=list[EmailAccountResponse])
async def list_accounts(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EmailAccount]:
    result = await db.execute(
        select(EmailAccount).where(EmailAccount.organization_id == uuid.UUID(current_user.organization_id))
    )
    return list(result.scalars().all())


@router.post("/accounts/{account_id}/sync", response_model=SyncResponse)
async def sync(
    account_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.id == account_id,
            EmailAccount.organization_id == uuid.UUID(current_user.organization_id),
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email account not found.")

    refresh_token = decrypt_secret(account.refresh_token_encrypted)
    tokens = await GmailOAuthClient().refresh_access_token(refresh_token)
    ingested = await sync_account(db, account, tokens.access_token)
    return SyncResponse(ingested=ingested)
