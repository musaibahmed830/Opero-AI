from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CRMContact:
    external_id: str
    name: str
    email: str
    company: str | None = None


class CRMConnector(ABC):
    """A connector to an *external* CRM (HubSpot/Salesforce/Pipedrive) — distinct
    from the native `Contact`/`Lead` tables in docs/DATABASE_DESIGN.md §3, which
    exist regardless of whether an external CRM is connected. This is the
    outward-sync path described in docs/DEVELOPMENT_ROADMAP.md Phase 4.
    """

    @abstractmethod
    async def find_contact_by_email(self, email: str) -> CRMContact | None: ...

    @abstractmethod
    async def upsert_contact(self, name: str, email: str, company: str | None = None) -> CRMContact: ...
