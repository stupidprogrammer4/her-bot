from datetime import time
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator


class WindowPolicy(BaseModel):
    timezone: str = "Asia/Tehran"
    start: time = time(18)
    end: time = time(2)
    tracks: int = Field(default=3, ge=1, le=10)
    text_min: int = Field(default=1, ge=0, le=10)
    text_max: int = Field(default=5, ge=0, le=10)
    grace_seconds: int = Field(default=300, ge=1, le=1800)
    cooldown_windows: int = Field(default=7, ge=0, le=90)
    bootstrap_min_seconds: int = Field(default=60, ge=1, le=600)

    @model_validator(mode="after")
    def valid(self) -> Self:
        ZoneInfo(self.timezone)
        if self.start == self.end or self.text_min > self.text_max:
            raise ValueError("Invalid window or text range")
        return self


class AccessPolicy(BaseModel):
    owner_id: int = Field(gt=0)
    channel_id: int = Field(lt=0)
    group_id: int | None = Field(default=None, lt=0)
    group_enabled: bool = False
    paused: bool = True


class ModelPolicy(BaseModel):
    model: str = Field(min_length=1, max_length=150)
    temperature: float = Field(default=0.7, ge=0, le=2)
    chat_tokens: int = Field(default=320, ge=50, le=2000)
    technical_tokens: int = Field(default=900, ge=50, le=4000)
    caption_tokens: int = Field(default=220, ge=50, le=500)
    max_daily_calls: int = Field(default=150, ge=1, le=10000)
    max_rounds: int = Field(default=4, ge=1, le=8)
    history_messages: int = Field(default=12, ge=2, le=40)
    history_chars: int = Field(default=8000, ge=500, le=20000)
    history_days: int = Field(default=7, ge=1, le=30)
    context_limit: int = Field(default=30, ge=1, le=100)
    context_chars: int = Field(default=10000, ge=1000, le=30000)
    channel_days: int = Field(default=90, ge=1, le=365)
    minimum_chat_seconds: int = Field(default=5, ge=1, le=60)
    hourly_chat_limit: int = Field(default=30, ge=1, le=300)


class PersonaFact(BaseModel):
    key: str = Field(min_length=1, max_length=60)
    content: str = Field(min_length=1, max_length=500)
    visibility: Literal["public_persona", "owner_private"] = "public_persona"
    source: Literal["owner_report"] = "owner_report"


class PersonaPolicy(BaseModel):
    display_name: str = Field(default="شمع زیبا", min_length=1, max_length=40)
    aliases: list[str] = Field(default_factory=lambda: ["شمع زیبا", "Her"])
    system_prompt: str = Field(min_length=100, max_length=16000)
    facts: list[PersonaFact] = Field(default_factory=list, max_length=50)
    topics: list[str] = Field(min_length=1, max_length=30)
    fallbacks: dict[str, list[str]] = Field(default_factory=dict)
    music_fallback: str = "اینم برای امشب 🎧"
    greeting_fallback: str = "سلام بچه‌هاا :))) شمع زیبام 🎀🍓"
    chat_fallback: str = "الان جوابم گیر کرده، یه کم بعد دوباره بگو"
    owner_address: str = ""


class SettingsSnapshot(BaseModel):
    access_revision: int = Field(ge=1)
    access: AccessPolicy
    window: WindowPolicy
    model: ModelPolicy
    persona: PersonaPolicy


class SettingWrite(BaseModel):
    revision: int = Field(ge=1)
    value: AccessPolicy | WindowPolicy | ModelPolicy | PersonaPolicy
