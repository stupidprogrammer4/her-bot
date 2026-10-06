import json

from papilio.infra.db.repositories.backends.mysql import MySQLReader
from sqlalchemy import func, select
from sqlmodel import col

from her_api.modules.content.channel.infra.tables import (
    ChannelCoverageTable,
    ChannelPostTable,
)
from her_api.shared.dates import as_utc
from her_contracts.channel import ChannelContext, ChannelPostWrite


class ChannelReader(MySQLReader):
    async def context(
        self,
        channel_id: int,
        limit: int,
        max_chars: int,
        query: str | None = None,
    ) -> ChannelContext:
        table = ChannelPostTable
        stmt = select(table).where(
            col(table.channel_id) == channel_id, col(table.active).is_(True)
        )
        if query:
            escaped = (
                query.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            stmt = stmt.where(
                col(table.text).like("%" + escaped + "%", escape="\\")
                | col(table.caption).like("%" + escaped + "%", escape="\\")
            )
        result = await self.uow.execute(
            stmt.order_by(
                col(table.posted_at).desc(), col(table.message_id).desc()
            ).limit(limit)
        )
        rows = list(result.scalars())
        bounds = await self.uow.execute(
            select(
                func.min(col(table.posted_at)),
                func.max(col(table.posted_at)),
                func.max(col(table.updated_at)),
            ).where(col(table.channel_id) == channel_id)
        )
        earliest, latest, updated = bounds.one()
        coverage_result = await self.uow.execute(
            select(ChannelCoverageTable).where(
                col(ChannelCoverageTable.channel_id) == channel_id
            )
        )
        coverage = coverage_result.scalar_one_or_none()
        posts, used = [], 0
        for row in rows:
            length = len(row.text) + len(row.caption)
            if used + length > max_chars:
                break
            used += length
            posts.append(
                ChannelPostWrite(
                    **row.model_dump(exclude={"posted_at", "edited_at"}),
                    posted_at=as_utc(row.posted_at),
                    edited_at=as_utc(row.edited_at) if row.edited_at else None,
                )
            )
        return ChannelContext(
            posts=list(reversed(posts)),
            earliest=as_utc(earliest) if earliest else None,
            latest=as_utc(latest) if latest else None,
            last_update_received_at=as_utc(coverage.last_update_received_at)
            if coverage and coverage.last_update_received_at
            else None,
            gaps=(
                ["history_before_first_observation_unavailable"]
                if rows
                else ["no_stored_history"]
            )
            + [
                json.dumps(g, ensure_ascii=False)
                for g in json.loads(coverage.gaps_json)
                if g
            ]
            if coverage
            else ["history_before_first_observation_unavailable"],
        )
