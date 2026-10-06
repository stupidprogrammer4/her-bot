from datetime import datetime
from typing import Any, cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.sql.elements import ColumnClause
from sqlmodel import col

from her_api.modules.conversations.actions.domain.dtos import ActionChange
from her_api.modules.conversations.actions.domain.models import (
    DeleteConfirmationModel,
    OwnerActionModel,
)
from her_api.modules.conversations.actions.infra.tables import (
    DeleteConfirmationTable,
    OwnerActionTable,
)


class OwnerActionRepository(MySQLRepository[OwnerActionModel]):
    table = OwnerActionTable

    async def by_update(self, update_id: int) -> OwnerActionModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.update_id) == update_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def reserve(self, data: OwnerActionModel) -> bool:
        await self.upsert(
            data,
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.update_id) == data.update_id,
                col(self.table.status) == "reserved",
            )
            .values(status="executing")
        )
        return cast(CursorResult, result).rowcount == 1

    async def finish(self, update_id: int, change: ActionChange) -> None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.update_id) == update_id)
            .values(**change.model_dump())
        )


class DeleteConfirmationRepository(MySQLRepository[DeleteConfirmationModel]):
    table = DeleteConfirmationTable

    async def by_token(self, token: str) -> DeleteConfirmationModel | None:
        result = await self.uow.execute(
            select(self.table).where(col(self.table.token) == token)
        )
        return result.scalar_one_or_none()

    async def claim(
        self, token: str, actor_id: int, channel_id: int, now: datetime
    ) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.token) == token,
                col(self.table.owner_id) == actor_id,
                col(self.table.channel_id) == channel_id,
                col(self.table.expires_at) > now,
                col(self.table.status) == "pending",
            )
            .values(status="confirmed")
            .execution_options(synchronize_session=False)
        )
        return cast(CursorResult, result).rowcount == 1
