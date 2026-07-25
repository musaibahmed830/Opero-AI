import uuid

from opero_connectors.crm_connector import CRMConnector, CRMContact


class MockCRMConnector(CRMConnector):
    def __init__(self, seed_contacts: list[CRMContact] | None = None) -> None:
        self._contacts_by_email = {c.email: c for c in (seed_contacts or [])}

    async def find_contact_by_email(self, email: str) -> CRMContact | None:
        return self._contacts_by_email.get(email)

    async def upsert_contact(self, name: str, email: str, company: str | None = None) -> CRMContact:
        existing = self._contacts_by_email.get(email)
        contact = CRMContact(
            external_id=existing.external_id if existing else f"mock-contact-{uuid.uuid4().hex[:12]}",
            name=name,
            email=email,
            company=company,
        )
        self._contacts_by_email[email] = contact
        return contact
