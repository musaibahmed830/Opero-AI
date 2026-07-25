import uuid
from datetime import datetime

from pydantic import BaseModel


class ConnectResponse(BaseModel):
    authorization_url: str


class CallbackResponse(BaseModel):
    connected: bool
    email_address: str


class SyncResponse(BaseModel):
    ingested: int


class EmailAccountResponse(BaseModel):
    id: uuid.UUID
    email_address: str
    connected_at: datetime
    last_synced_at: datetime | None

    model_config = {"from_attributes": True}
