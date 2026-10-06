from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from her_contracts.channel import ChannelPostWrite
from her_contracts.media import AudioUpload

ChatType = Literal["private", "group", "supergroup", "channel"]


class IncomingMessage(BaseModel):
    update_id: int = Field(ge=0)
    message_id: int = Field(gt=0)
    chat_id: int
    chat_type: ChatType
    sender_id: int | None = None
    sender_is_bot: bool = False
    sender_chat_id: int | None = None
    text: str = Field(default="", max_length=16000)
    addressed: bool = False
    audio: AudioUpload | None = None
    channel_post: bool = False
    posted_at: AwareDatetime
    edited_at: AwareDatetime | None = None
    callback_query_id: str | None = Field(default=None, max_length=128)
    forwarded_post: ChannelPostWrite | None = None


class Admission(BaseModel):
    accepted: bool
    replay: bool = False
    task_id: str | None = None


class BotConfiguration(BaseModel):
    owner_id: int
    channel_id: int
    group_id: int | None
    display_name: str
    aliases: list[str]
