from her_api.modules.ops.settings.infra.readers import SettingsReader
from her_contracts.policy import (
    AccessPolicy,
    ModelPolicy,
    OccasionPolicy,
    PersonaPolicy,
    SettingsSnapshot,
    WindowPolicy,
)


class SettingsQueries:
    def __init__(self, reader: SettingsReader):
        self.reader = reader

    async def snapshot(self) -> SettingsSnapshot:
        values = await self.reader.values()
        if (
            not {"access", "model", "persona", "window", "occasions"}
            <= values.keys()
        ):
            raise ValueError("Settings missing; run the bootstrap command")
        return SettingsSnapshot(
            occasions=OccasionPolicy.model_validate_json(
                values["occasions"].value
            ),
            access_revision=values["access"].revision,
            access=AccessPolicy.model_validate_json(values["access"].value),
            model=ModelPolicy.model_validate_json(values["model"].value),
            persona=PersonaPolicy.model_validate_json(values["persona"].value),
            window=WindowPolicy.model_validate_json(values["window"].value),
        )
