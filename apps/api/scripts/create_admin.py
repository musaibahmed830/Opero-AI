"""CLI convenience wrapper around the same bootstrap logic POST /v1/auth/register
uses — for scripted/automated setup (`make create-admin`) without needing to
curl the API. Usage:

    python scripts/create_admin.py --org "Acme Inc" --email owner@acme.com --password ...
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.services.auth_service import register_organization_and_owner  # noqa: E402


async def main(organization_name: str, email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        try:
            organization, user = await register_organization_and_owner(
                db, organization_name=organization_name, email=email, password=password
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    print(f"Created organization '{organization.name}' ({organization.id})")
    print(f"Created owner user '{user.email}' ({user.id})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True, dest="organization_name")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    asyncio.run(main(args.organization_name, args.email, args.password))
