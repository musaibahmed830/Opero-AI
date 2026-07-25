"""RBAC seed data and the permission-check dependency (docs/SECURITY_MODEL.md §4).

Permissions are a fixed, codebase-defined set (docs/DATABASE_DESIGN.md §3) —
customers don't invent new permission codes, only assign the existing ones to
roles. MVP seeds exactly three roles per organization (owner/admin/member);
custom roles are a later feature the schema already supports.
"""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.models.permission import Permission
from app.models.role import Role
from app.models.user_role import UserRole

# Every permission code the system can check for. Adding a new checkable
# capability means adding a code here — the set is fixed by the codebase.
PERMISSION_CODES = [
    "email.read",
    "email.send",
    "leads.read",
    "leads.write",
    "tasks.read",
    "tasks.write",
    "approvals.read",
    "approvals.decide",
    "integrations.manage",
    "documents.read",
    "documents.write",
    "audit.read",
    "reports.read",
    "reports.generate",
]

DEFAULT_ROLES: dict[str, list[str]] = {
    "owner": PERMISSION_CODES,  # everything
    "admin": [c for c in PERMISSION_CODES if c != "integrations.manage"],
    "member": [
        "email.read",
        "leads.read",
        "tasks.read",
        "tasks.write",
        "approvals.read",
        "documents.read",
        "reports.read",
    ],
}


async def ensure_global_permissions(db: AsyncSession) -> dict[str, Permission]:
    """Get-or-create every permission code. Idempotent — safe to call on every
    organization bootstrap since permissions are global, not per-organization.
    """
    result = await db.execute(select(Permission))
    by_code = {p.code: p for p in result.scalars().all()}

    for code in PERMISSION_CODES:
        if code not in by_code:
            permission = Permission(code=code, description="")
            db.add(permission)
            by_code[code] = permission

    await db.flush()
    return by_code


async def seed_default_roles(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Role]:
    permissions_by_code = await ensure_global_permissions(db)
    roles: dict[str, Role] = {}

    for role_name, codes in DEFAULT_ROLES.items():
        role = Role(organization_id=organization_id, name=role_name, description="")
        role.permissions = [permissions_by_code[code] for code in codes]
        db.add(role)
        roles[role_name] = role

    await db.flush()
    return roles


async def _user_permission_codes(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    result = await db.execute(
        select(Permission.code)
        .join(Role.permissions)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return set(result.scalars().all())


def require_permission(code: str):
    """Dependency factory: `Depends(require_permission("approvals.decide"))`.

    Raises 403 if the authenticated user holds no role granting `code` in
    their organization. A real DB-backed check, not a token-embedded claim —
    permission changes take effect immediately without a new login.
    """

    async def _dependency(
        current_user: AuthenticatedUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> AuthenticatedUser:
        codes = await _user_permission_codes(db, uuid.UUID(current_user.subject))
        if code not in codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {code}",
            )
        return current_user

    return _dependency
