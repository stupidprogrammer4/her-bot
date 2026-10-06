from datetime import datetime, timedelta
from typing import Any, cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.sql.elements import ColumnClause
from sqlmodel import col

from her_api.modules.ops.inbox.domain.dtos import InboxChange
from her_api.modules.ops.inbox.domain.models import InboxModel
from her_api.modules.ops.inbox.infra.tables import InboxTable


class InboxRepository(MySQLRepository[InboxModel]):
    table = InboxTable

    async def by_update(self, update_id: int) -> InboxModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.update_id) == update_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def admit(self, data: InboxModel) -> None:
        await self.upsert(
            data,
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )

    async def claim(self, update_id: int, now: datetime) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.update_id) == update_id,
                col(self.table.status) == "pending",
            )
            .values(
                status="running", lease_expires_at=now + timedelta(seconds=90)
            )
        )
        return cast(CursorResult, result).rowcount == 1

    async def finish(self, update_id: int, data: InboxChange) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.update_id) == update_id,
                col(self.table.status) == "running",
            )
            .values(**data.model_dump())
        )

    async def recover(self, now: datetime) -> list[int]:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.status) == "running",
                col(self.table.lease_expires_at) <= now,
            )
            .values(status="pending", lease_expires_at=None)
        )
        result = await self.uow.execute(
            select(col(self.table.update_id))
            .where(col(self.table.status) == "pending")
            .order_by(col(self.table.id))
            .limit(30)
        )
        return list(result.scalars())

    async def purge(self, before: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.created_at) < before,
                col(self.table.status).in_(["completed", "failed"]),
            )
            .values(payload="{}")
        )
