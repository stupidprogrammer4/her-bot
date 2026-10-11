from typing import Literal

from pydantic import BaseModel, Field

from her_contracts.policy import (
    AccessPolicy,
    ModelPolicy,
    OccasionPolicy,
    PersonaPolicy,
    WindowPolicy,
)

SettingKey = Literal["access", "window", "model", "persona", "occasions"]
SettingValue = (
    AccessPolicy | WindowPolicy | ModelPolicy | PersonaPolicy | OccasionPolicy
)


class SettingChange(BaseModel):
    value: str
    revision: int = Field(ge=1)


class SettingOut(BaseModel):
    key: SettingKey
    revision: int
    value: SettingValue
