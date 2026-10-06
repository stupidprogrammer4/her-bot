from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import func, select, update
from sqlmodel import col

from her_api.modules.library.tracks.domain.dtos import TrackChange
from her_api.modules.library.tracks.domain.models import TrackModel
from her_api.modules.library.tracks.infra.tables import TrackTable
from her_contracts.media import AudioUpload


class TrackRepository(MySQLRepository[TrackModel]):
    table = TrackTable

    async def get(self, id: int) -> TrackModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.id) == id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def upload(self, data: AudioUpload, tags_json: str) -> TrackModel:
        model = TrackModel(
            **data.model_dump(exclude={"tags"}), tags_json=tags_json
        )
        fields = [
            col(self.table.bot_id),
            col(self.table.file_id),
            col(self.table.source_chat_id),
            col(self.table.source_message_id),
            col(self.table.title),
            col(self.table.performer),
            col(self.table.filename),
            col(self.table.duration),
            col(self.table.file_size),
            col(self.table.mood),
            col(self.table.tags_json),
        ]
        await self.upsert(model, update_columns=fields)
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.file_unique_id) == data.file_unique_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()

    async def change(self, id: int, data: TrackChange) -> None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.id) == id)
            .values(**data.model_dump(exclude_unset=True))
        )

    async def page(
        self, page: int, per_page: int, mood: str | None = None
    ) -> tuple[list[TrackModel], int]:
        stmt = select(self.table)
        if mood is not None:
            stmt = stmt.where(
                col(self.table.mood) == mood, col(self.table.active).is_(True)
            )
        count = await self.uow.execute(
            select(func.count()).select_from(stmt.subquery())
        )
        rows = await self.uow.execute(
            stmt.order_by(col(self.table.id))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(rows.scalars()), count.scalar_one()
