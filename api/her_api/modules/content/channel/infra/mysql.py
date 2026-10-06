from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.sql.elements import ColumnClause
from sqlmodel import col

from her_api.modules.content.channel.domain.models import (
    ChannelCoverageModel,
    ChannelImportModel,
    ChannelPostModel,
    ImportSessionModel,
)
from her_api.modules.content.channel.infra.tables import (
    ChannelCoverageTable,
    ChannelImportTable,
    ChannelPostTable,
    ImportSessionTable,
)


class ChannelPostRepository(MySQLRepository[ChannelPostModel]):
    table = ChannelPostTable

    async def write(self, data: ChannelPostModel) -> None:
        columns = ChannelPostTable.metadata.tables["tbl_channel_posts"].c
        await self.upsert(
            data,
            update_columns=[
                columns.text,
                columns.caption,
                columns.posted_at,
                columns.edited_at,
                columns.media_kind,
                columns.active,
            ],
        )

    async def write_many(self, rows: Sequence[ChannelPostModel]) -> None:
        if not rows:
            return
        columns = ChannelPostTable.metadata.tables["tbl_channel_posts"].c
        await self.bulk_upsert(
            rows,
            insert_columns={
                "channel_id": columns.channel_id,
                "message_id": columns.message_id,
                "text": columns.text,
                "caption": columns.caption,
                "posted_at": columns.posted_at,
                "edited_at": columns.edited_at,
                "media_kind": columns.media_kind,
                "origin": columns.origin,
                "active": columns.active,
            },
            update_columns=[
                columns.text,
                columns.caption,
                columns.posted_at,
                columns.edited_at,
                columns.media_kind,
                columns.active,
            ],
        )

    async def deactivate(self, channel_id: int, message_id: int) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.channel_id) == channel_id,
                col(self.table.message_id) == message_id,
            )
            .values(active=False)
        )

    async def purge(self, before: datetime) -> None:
        await self.uow.execute(
            delete(self.table).where(col(self.table.posted_at) < before)
        )


class ChannelImportRepository(MySQLRepository[ChannelImportModel]):
    table = ChannelImportTable

    async def by_update(self, update_id: int) -> ChannelImportModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.update_id) == update_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def reserve_update(
        self, data: ChannelImportModel
    ) -> ChannelImportModel:
        if data.update_id is None:
            raise ValueError("Update identity required")
        await self.upsert(
            data,
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(
                    self.table.id
                ),
            },
        )
        row = await self.by_update(data.update_id)
        if row is None:
            raise ValueError("Import reservation failed")
        return row

    async def by_token(self, token: str) -> ChannelImportModel | None:
        result = await self.uow.execute(
            select(self.table).where(col(self.table.token) == token)
        )
        return result.scalar_one_or_none()

    async def consumed(self, id: int) -> None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.id) == id)
            .values(status="imported", payload="[]")
        )

    async def claim(self, id: int) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id, col(self.table.status) == "preview"
            )
            .values(status="importing")
        )
        return cast(CursorResult, result).rowcount == 1

    async def purge(self, now: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.expires_at) <= now,
                col(self.table.status) == "preview",
            )
            .values(payload="[]", status="expired")
        )


class ImportSessionRepository(MySQLRepository[ImportSessionModel]):
    table = ImportSessionTable

    async def open(self, actor_id: int, expires_at: datetime) -> None:
        columns = ImportSessionTable.metadata.tables["tbl_import_sessions"].c
        await self.upsert(
            ImportSessionModel(owner_id=actor_id, expires_at=expires_at),
            update_columns=[columns.expires_at],
        )

    async def get(self, actor_id: int) -> ImportSessionModel | None:
        result = await self.uow.execute(
            select(self.table).where(col(self.table.owner_id) == actor_id)
        )
        return result.scalar_one_or_none()


class ChannelCoverageRepository(MySQLRepository[ChannelCoverageModel]):
    table = ChannelCoverageTable

    async def get(self, channel_id: int) -> ChannelCoverageModel | None:
        result = await self.uow.execute(
            select(self.table).where(col(self.table.channel_id) == channel_id)
        )
        return result.scalar_one_or_none()

    async def observe(self, channel_id: int, now: datetime) -> None:
        columns = ChannelCoverageTable.metadata.tables[
            "tbl_channel_coverages"
        ].c
        await self.upsert(
            ChannelCoverageModel(
                channel_id=channel_id, last_update_received_at=now
            ),
            update_columns=[columns.last_update_received_at],
        )

    async def heartbeat(
        self, channel_id: int, now: datetime, gaps_json: str
    ) -> None:
        columns = ChannelCoverageTable.metadata.tables[
            "tbl_channel_coverages"
        ].c
        await self.upsert(
            ChannelCoverageModel(
                channel_id=channel_id,
                last_heartbeat_at=now,
                gaps_json=gaps_json,
            ),
            update_columns=[columns.last_heartbeat_at, columns.gaps_json],
        )
