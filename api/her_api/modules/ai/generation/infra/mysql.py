from datetime import date
from typing import Any, cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.sql.elements import ColumnClause
from sqlmodel import col

from her_api.modules.ai.generation.domain.dtos import ModelCallChange
from her_api.modules.ai.generation.domain.models import (
    DailyCallModel,
    ModelCallModel,
)
from her_api.modules.ai.generation.infra.tables import (
    DailyCallTable,
    ModelCallTable,
)


class DailyCallRepository(MySQLRepository[DailyCallModel]):
    table = DailyCallTable

    async def reserve(self, day: date, maximum: int) -> bool:
        await self.upsert(
            DailyCallModel(day=day, calls=0),
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )
        result = await self.uow.execute(
            update(self.table)
            .where(col(self.table.day) == day, col(self.table.calls) < maximum)
            .values(calls=col(self.table.calls) + 1)
        )
        return cast(CursorResult, result).rowcount == 1


class ModelCallRepository(MySQLRepository[ModelCallModel]):
    table = ModelCallTable

    async def finish(
        self,
        id: int,
        data: ModelCallChange,
    ) -> None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.id) == id)
            .values(**data.model_dump())
        )
