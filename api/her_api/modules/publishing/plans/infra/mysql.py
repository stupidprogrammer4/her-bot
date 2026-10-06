from datetime import date
from typing import Any, cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.sql.elements import ColumnClause
from sqlmodel import col

from her_api.modules.publishing.plans.domain.dtos import PlanChange
from her_api.modules.publishing.plans.domain.models import PlanModel
from her_api.modules.publishing.plans.infra.tables import PlanTable


class PlanRepository(MySQLRepository[PlanModel]):
    table = PlanTable

    async def for_evening(
        self, channel_id: int, day: date
    ) -> PlanModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.channel_id) == channel_id,
                col(self.table.evening_date) == day,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def change(self, id: int, data: PlanChange) -> None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.id) == id)
            .values(**data.model_dump(exclude_unset=True))
        )

    async def ensure(self, data: PlanModel) -> PlanModel:
        await self.upsert(
            data,
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )
        row = await self.for_evening(data.channel_id, data.evening_date)
        if row is None:
            raise ValueError("Plan not found after creation")
        return row

    async def claim_text(self, id: int, count: int, now) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id, col(self.table.text_count).is_(None)
            )
            .values(text_count=count, text_created_at=now)
        )
        return cast(CursorResult, result).rowcount == 1

    async def claim_music(self, id: int) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id,
                col(self.table.music_status) == "waiting_for_tracks",
            )
            .values(music_status="planned")
        )
        return cast(CursorResult, result).rowcount == 1

    async def claim_warning(self, id: int) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id,
                col(self.table.warned_missing_tracks).is_(False),
            )
            .values(warned_missing_tracks=True)
        )
        return cast(CursorResult, result).rowcount == 1
