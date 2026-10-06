from datetime import datetime

from pydantic import BaseModel


class ChatChange(BaseModel):
    messages: str | None = None
    capabilities: str | None = None
    phase: str | None = None
    status: str | None = None
    round: int | None = None
    tool_cursor: int | None = None
    started_at: datetime | None = None
    next_attempt_at: datetime | None = None
    lease_expires_at: datetime | None = None


class ConversationAdmission(BaseModel):
    hourly_count: int
    latest_at: datetime | None
