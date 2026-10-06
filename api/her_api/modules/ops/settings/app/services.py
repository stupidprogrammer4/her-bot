from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.tools.decorators import transactional

from her_api.modules.ops.settings.domain.dtos import (
    SettingChange,
    SettingKey,
    SettingOut,
    SettingValue,
)
from her_api.modules.ops.settings.domain.models import SettingModel
from her_api.modules.ops.settings.infra.mysql import SettingRepository
from her_api.modules.persona.privacy.app.guard import IdentityGuard
from her_contracts.policy import (
    AccessPolicy,
    ModelPolicy,
    PersonaPolicy,
    WindowPolicy,
)

VALUE_TYPES = {
    "access": AccessPolicy,
    "model": ModelPolicy,
    "persona": PersonaPolicy,
    "window": WindowPolicy,
}


class SettingsService:
    def __init__(self, repo: SettingRepository, guard: IdentityGuard):
        self.repo = repo
        self.guard = guard

    async def get(self, key: SettingKey) -> SettingOut:
        row = await self.repo.by_key(key)
        if row is None:
            raise NotFoundException(
                "Setting not found", "record_not_found", "setting", "key", key
            )
        return SettingOut(
            key=key,
            revision=row.revision,
            value=VALUE_TYPES[key].model_validate_json(row.value),
        )

    @transactional
    async def write(
        self, key: SettingKey, value: SettingValue, revision: int
    ) -> SettingOut:
        typed = VALUE_TYPES[key].model_validate(value.model_dump())
        self.guard.require_safe(typed.model_dump_json())
        row = await self.repo.by_key(key)
        if row is None:
            raise NotFoundException(
                "Setting not found", "record_not_found", "setting", "key", key
            )
        if row.revision != revision:
            raise ValueError("Settings changed; reload their revision")
        changed = await self.repo.change(
            row.id,
            SettingChange(
                value=typed.model_dump_json(), revision=revision + 1
            ),
            revision,
        )
        if not changed:
            raise ValueError("Settings changed; reload their revision")
        return SettingOut(key=key, revision=revision + 1, value=typed)

    @transactional
    async def bootstrap(self, key: SettingKey, value: SettingValue) -> None:
        typed = VALUE_TYPES[key].model_validate(value.model_dump())
        self.guard.require_safe(typed.model_dump_json())
        if await self.repo.by_key(key) is None:
            await self.repo.create(
                SettingModel(key=key, value=typed.model_dump_json())
            )
