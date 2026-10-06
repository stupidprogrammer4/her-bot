from typing import cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlmodel import col

from her_api.modules.ops.settings.domain.dtos import SettingChange
from her_api.modules.ops.settings.domain.models import SettingModel
from her_api.modules.ops.settings.infra.tables import SettingTable


class SettingRepository(MySQLRepository[SettingModel]):
    table = SettingTable

    async def by_key(self, key: str) -> SettingModel | None:
        stmt = (
            select(self.table)
            .where(col(self.table.key) == key)
            .execution_options(populate_existing=True)
        )
        result = await self.uow.execute(stmt)
        return result.scalar_one_or_none()

    async def change(
        self, id: int, data: SettingChange, expected_revision: int
    ) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id,
                col(self.table.revision) == expected_revision,
            )
            .values(**data.model_dump())
        )
        return cast(CursorResult, result).rowcount == 1
