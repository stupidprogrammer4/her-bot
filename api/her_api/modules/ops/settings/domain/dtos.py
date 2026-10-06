from typing import Literal

from pydantic import BaseModel, Field

from her_contracts.policy import (
    AccessPolicy,
    ModelPolicy,
    PersonaPolicy,
    WindowPolicy,
)

SettingKey = Literal["access", "window", "model", "persona"]
SettingValue = AccessPolicy | WindowPolicy | ModelPolicy | PersonaPolicy


class SettingChange(BaseModel):
    value: str
    revision: int = Field(ge=1)


class SettingOut(BaseModel):
    key: SettingKey
    revision: int
    value: SettingValue
