from dishka import Provider, Scope, provide

from her_api.modules.ops.settings.app.queries import SettingsQueries
from her_api.modules.ops.settings.app.services import SettingsService
from her_api.modules.ops.settings.infra.mysql import SettingRepository
from her_api.modules.ops.settings.infra.readers import SettingsReader
from her_api.modules.ops.settings.interfaces import (
    ISettingsQueries,
    ISettingsService,
)
from her_contracts.policy import SettingsSnapshot


class SettingsProvider(Provider):
    scope = Scope.REQUEST
    repo = provide(SettingRepository)
    reader = provide(SettingsReader)
    queries = provide(SettingsQueries, provides=ISettingsQueries)
    service = provide(SettingsService, provides=ISettingsService)

    @provide
    async def snapshot(self, queries: ISettingsQueries) -> SettingsSnapshot:
        value = await queries.snapshot()
        return value
