from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

Destination = Literal["channel", "discussion_group", "owner"]
PublicationKind = Literal[
    "music", "text", "greeting", "preview", "edit", "delete", "reply"
]


class ManualPublication(BaseModel):
    update_id: int = Field(ge=0)
    actor_id: int = Field(gt=0)
    kind: PublicationKind
    destination: Destination = "channel"
    text: str | None = Field(default=None, max_length=700)
    track_id: int | None = Field(default=None, gt=0)
    target_message_id: int | None = Field(default=None, gt=0)


class JobOut(BaseModel):
    id: int
    kind: PublicationKind
    status: str
    scheduled_at: datetime
    message_id: int | None
    track_id: int | None
    topic: str | None
    text: str | None
    failure_reason: str | None


class Receipt(BaseModel):
    status: Literal["sent", "rate_limited", "failed", "delivery_unknown"]
    message_id: int | None = None
    retry_after: int | None = None
    reason: str | None = None


class TelegramSend(BaseModel):
    job_id: int
    chat_id: int
    kind: PublicationKind
    text: str = Field(max_length=4000)
    file_id: str | None = None
    reply_to: int | None = None
    target_message_id: int | None = None
    source_bot_id: int | None = None
    deadline_at: AwareDatetime | None = None
