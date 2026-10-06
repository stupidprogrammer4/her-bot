from papilio.infra.db.repositories.backends.mysql import MySQLReader
from sqlalchemy import select

from her_api.modules.ops.settings.domain.models import SettingModel
from her_api.modules.ops.settings.infra.tables import SettingTable


class SettingsReader(MySQLReader):
    async def values(self) -> dict[str, SettingModel]:
        result = await self.uow.execute(
            select(SettingTable).execution_options(populate_existing=True)
        )
        return {row.key: row for row in result.scalars()}
