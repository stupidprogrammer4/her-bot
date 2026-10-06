from datetime import datetime

from pydantic import BaseModel


class InboxChange(BaseModel):
    status: str
    lease_expires_at: datetime | None = None
    error_code: str | None = None
