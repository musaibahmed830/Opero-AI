from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.ai_employee import AIEmployee
from app.models.organization import Organization
from app.models.user import User
from app.models.user_role import UserRole
from app.services.rbac import seed_default_roles

DEFAULT_AI_EMPLOYEE_NAME = "Sales & Ops Assistant"


async def register_organization_and_owner(
    db: AsyncSession, *, organization_name: str, email: str, password: str
) -> tuple[Organization, User]:
    """Bootstraps a new self-hosted deployment: the organization, its default
    RBAC roles, its first (owner) user, and its AI employee
    (docs/PRODUCT_REQUIREMENTS.md §3a — one named role for MVP).

    Used by both POST /v1/auth/register and scripts/create_admin.py — one
    implementation, so the API and the CLI convenience script can never drift.
    """
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"A user with email {email} already exists.")

    organization = Organization(name=organization_name)
    db.add(organization)
    await db.flush()

    roles = await seed_default_roles(db, organization.id)

    user = User(organization_id=organization.id, email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.flush()

    db.add(UserRole(user_id=user.id, role_id=roles["owner"].id, organization_id=organization.id))
    db.add(AIEmployee(organization_id=organization.id, name=DEFAULT_AI_EMPLOYEE_NAME))

    await db.commit()
    await db.refresh(user)
    return organization, user
