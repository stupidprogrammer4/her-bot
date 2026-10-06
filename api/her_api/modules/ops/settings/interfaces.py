from collections.abc import Awaitable
from typing import Protocol

from her_api.modules.ops.settings.domain.dtos import (
    SettingKey,
    SettingOut,
    SettingValue,
)
from her_contracts.policy import SettingsSnapshot


class ISettingsQueries(Protocol):
    def snapshot(self) -> Awaitable[SettingsSnapshot]: ...


class ISettingsService(Protocol):
    def get(self, key: SettingKey) -> Awaitable[SettingOut]: ...
    def write(
        self, key: SettingKey, value: SettingValue, revision: int
    ) -> Awaitable[SettingOut]: ...
    def bootstrap(
        self, key: SettingKey, value: SettingValue
    ) -> Awaitable[None]: ...
