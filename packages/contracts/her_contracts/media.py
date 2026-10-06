from typing import Literal

from pydantic import BaseModel, Field

Mood = Literal["calm", "sad", "romantic", "energetic", "nostalgic", "neutral"]


class AudioUpload(BaseModel):
    bot_id: int = Field(gt=0)
    file_id: str = Field(min_length=1, max_length=512)
    file_unique_id: str = Field(min_length=1, max_length=128)
    source_chat_id: int
    source_message_id: int = Field(gt=0)
    title: str = Field(default="", max_length=300)
    performer: str = Field(default="", max_length=300)
    filename: str = Field(default="", max_length=300)
    duration: int = Field(ge=0)
    file_size: int | None = Field(default=None, ge=0)
    mood: Mood = "neutral"
    tags: list[str] = Field(default_factory=list, max_length=20)


class TrackOut(AudioUpload):
    id: int
    active: bool


class TrackPage(BaseModel):
    items: list[TrackOut]
    page: int
    total: int
