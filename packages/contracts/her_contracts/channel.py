from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field


class ChannelPostWrite(BaseModel):
    channel_id: int = Field(lt=0)
    message_id: int = Field(gt=0)
    text: str = Field(default="", max_length=10000)
    caption: str = Field(default="", max_length=2000)
    posted_at: AwareDatetime
    edited_at: AwareDatetime | None = None
    media_kind: str = Field(default="text", max_length=20)
    origin: Literal[
        "live", "own", "imported", "imported_unverified_mapping", "forward"
    ] = "live"


class ChannelContext(BaseModel):
    posts: list[ChannelPostWrite]
    earliest: datetime | None = None
    latest: datetime | None = None
    last_update_received_at: datetime | None = None
    gaps: list[str] = Field(default_factory=list)
    unknown_deletions: bool = True


class ImportPreview(BaseModel):
    token: str
    count: int
    invalid: int
    matching_channel: bool
    title: str
    earliest: datetime | None
    latest: datetime | None
