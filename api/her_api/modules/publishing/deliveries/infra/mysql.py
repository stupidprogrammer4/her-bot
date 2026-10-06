from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import bindparam, exists, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.sql.elements import ColumnClause
from sqlmodel import col

from her_api.modules.library.tracks.infra.tables import TrackTable
from her_api.modules.ops.settings.infra.tables import SettingTable
from her_api.modules.publishing.deliveries.domain.dtos import (
    JobChange,
    TrackReplacement,
)
from her_api.modules.publishing.deliveries.domain.models import (
    DeliveryGateModel,
    PublicationJobModel,
)
from her_api.modules.publishing.deliveries.infra.tables import (
    DeliveryGateTable,
    PublicationJobTable,
)


class PublicationRepository(MySQLRepository[PublicationJobModel]):
    table = PublicationJobTable

    async def reserve(self, data: PublicationJobModel) -> PublicationJobModel:
        await self.upsert(
            data,
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )
        row = await self.for_update(data.update_id or 0)
        if row is None:
            raise ValueError("Publication reservation failed")
        return row

    async def reply(self, data: PublicationJobModel) -> None:
        await self.upsert(
            data,
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )

    async def owned_post(
        self, channel_id: int, message_id: int
    ) -> PublicationJobModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.channel_id) == channel_id,
                col(self.table.message_id) == message_id,
                col(self.table.status) == "sent",
                col(self.table.kind).in_(["text", "greeting", "edit"]),
            )
            .order_by(col(self.table.id).desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def recent(self, limit: int) -> list[PublicationJobModel]:
        result = await self.uow.execute(
            select(self.table).order_by(col(self.table.id).desc()).limit(limit)
        )
        return list(result.scalars())

    async def notify(
        self, parent: PublicationJobModel, text: str, now: datetime
    ) -> None:
        await self.upsert(
            PublicationJobModel(
                parent_job_id=parent.id,
                kind="reply",
                channel_id=parent.owner_id,
                owner_id=parent.owner_id,
                automatic=False,
                text=text,
                scheduled_at=now,
                next_attempt_at=now,
            ),
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )

    async def notify_many(self, rows: Sequence[PublicationJobModel]) -> None:
        if not rows:
            return
        columns = self.table.metadata.tables["tbl_publication_jobs"].c
        await self.bulk_upsert(
            rows,
            insert_columns={
                "parent_job_id": columns.parent_job_id,
                "kind": columns.kind,
                "channel_id": columns.channel_id,
                "owner_id": columns.owner_id,
                "automatic": columns.automatic,
                "text": columns.text,
                "scheduled_at": columns.scheduled_at,
                "next_attempt_at": columns.next_attempt_at,
            },
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )

    async def get(self, id: int) -> PublicationJobModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.id) == id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def for_update(self, update_id: int) -> PublicationJobModel | None:
        result = await self.uow.execute(
            select(self.table).where(
                col(self.table.update_id) == update_id,
                col(self.table.write_slot) == 1,
            )
        )
        return result.scalar_one_or_none()

    async def create_many(self, rows: Sequence[PublicationJobModel]) -> None:
        columns = PublicationJobTable.metadata.tables["tbl_publication_jobs"].c
        await self.bulk_insert(
            rows,
            insert_columns={
                "plan_id": columns.plan_id,
                "kind": columns.kind,
                "ordinal": columns.ordinal,
                "track_id": columns.track_id,
                "channel_id": columns.channel_id,
                "owner_id": columns.owner_id,
                "scheduled_at": columns.scheduled_at,
                "deadline_at": columns.deadline_at,
                "next_attempt_at": columns.next_attempt_at,
                "topic": columns.topic,
            },
        )

    async def due_ids(self, now: datetime, limit: int = 30) -> list[int]:
        j = self.table
        result = await self.uow.execute(
            select(col(j.id))
            .where(
                col(j.status) == "pending",
                col(j.text).is_not(None) | (col(j.kind) == "delete"),
                col(j.scheduled_at) <= now,
                col(j.next_attempt_at) <= now,
            )
            .order_by(col(j.next_attempt_at), col(j.id))
            .limit(limit)
        )
        return list(result.scalars())

    async def preparation_ids(
        self, now: datetime, include_automatic: bool, limit: int = 30
    ) -> list[int]:
        j = self.table
        stmt = select(col(j.id)).where(
            col(j.status) == "pending",
            col(j.text).is_(None),
            col(j.kind) != "delete",
            col(j.deadline_at).is_(None) | (col(j.deadline_at) > now),
        )
        if not include_automatic:
            stmt = stmt.where(col(j.automatic).is_(False))
        result = await self.uow.execute(
            stmt.order_by(col(j.scheduled_at), col(j.id)).limit(limit)
        )
        return list(result.scalars())

    async def claim_generation(
        self, id: int, now: datetime, include_automatic: bool
    ) -> bool:
        j = self.table
        stmt = update(j).where(
            col(j.id) == id,
            col(j.status) == "pending",
            col(j.text).is_(None),
            col(j.kind) != "delete",
            col(j.deadline_at).is_(None) | (col(j.deadline_at) > now),
        )
        if not include_automatic:
            stmt = stmt.where(col(j.automatic).is_(False))
        result = await self.uow.execute(
            stmt.values(
                status="preparing",
                preparing_started_at=now,
                lease_expires_at=now + timedelta(seconds=90),
            )
        )
        return cast(CursorResult, result).rowcount == 1

    async def finish_generation(
        self, id: int, started_at: datetime, change: JobChange
    ) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id,
                col(self.table.status) == "preparing",
                col(self.table.preparing_started_at) == started_at,
                col(self.table.text).is_(None),
            )
            .values(**change.model_dump(exclude_unset=True))
            .execution_options(synchronize_session=False)
        )

    async def claim_delivery(self, id: int, now: datetime) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id,
                col(self.table.status) == "pending",
                col(self.table.text).is_not(None)
                | (col(self.table.kind) == "delete"),
                col(self.table.scheduled_at) <= now,
                col(self.table.next_attempt_at) <= now,
            )
            .values(
                status="preparing",
                preparing_started_at=now,
                lease_expires_at=now + timedelta(seconds=90),
            )
        )
        return cast(CursorResult, result).rowcount == 1

    async def claim_sending(
        self,
        id: int,
        now: datetime,
        access_revision: int,
        track_id: int | None,
        file_id: str | None,
    ) -> bool:
        access_unchanged = exists(
            select(col(SettingTable.id)).where(
                col(SettingTable.key) == "access",
                col(SettingTable.revision) == access_revision,
            )
        )
        track_unchanged = (
            col(self.table.track_id).is_(None)
            if track_id is None
            else (
                (col(self.table.track_id) == track_id)
                & exists(
                    select(col(TrackTable.id)).where(
                        col(TrackTable.id) == track_id,
                        col(TrackTable.active).is_(True),
                        col(TrackTable.file_id) == file_id,
                    )
                )
            )
        )
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id,
                col(self.table.status) == "preparing",
                access_unchanged,
                track_unchanged,
            )
            .values(
                status="sending",
                send_started_at=now,
                lease_expires_at=now + timedelta(seconds=60),
                attempts=col(self.table.attempts) + 1,
            )
        )
        return cast(CursorResult, result).rowcount == 1

    async def change(
        self, id: int, data: JobChange, *, expected: str | None = None
    ) -> None:
        stmt = update(self.table).where(col(self.table.id) == id)
        if expected is not None:
            stmt = stmt.where(col(self.table.status) == expected)
        await self.uow.execute(
            stmt.values(**data.model_dump(exclude_unset=True))
        )

    async def replace_many(self, rows: Sequence[TrackReplacement]) -> None:
        if not rows:
            return
        table = self.table.metadata.tables["tbl_publication_jobs"]
        stmt = (
            update(table)
            .where(
                table.c.id == bindparam("job_id"),
                table.c.status.in_(["pending", "blocked"]),
            )
            .values(
                track_id=bindparam("new_track"),
                text=None,
                status=bindparam("new_status"),
            )
        )
        await self.uow.execute(
            stmt,
            [
                {
                    "job_id": r.job_id,
                    "new_track": r.track_id,
                    "new_status": "pending"
                    if r.track_id is not None
                    else "blocked",
                }
                for r in rows
            ],
        )

    async def recover(self, now: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.status) == "sending",
                col(self.table.lease_expires_at) <= now,
            )
            .values(
                status="delivery_unknown",
                failure_reason="delivery_interrupted",
            )
        )
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.status) == "preparing",
                col(self.table.lease_expires_at) <= now,
            )
            .values(status="pending", lease_expires_at=None)
        )
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.automatic).is_(True),
                col(self.table.status).in_(["pending", "blocked"]),
                col(self.table.deadline_at) <= now,
            )
            .values(status="expired")
        )

    async def purge_private_text(self, before: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.kind) == "reply",
                col(self.table.created_at) < before,
                col(self.table.status).in_(
                    ["sent", "failed", "delivery_unknown"]
                ),
            )
            .values(text="")
        )


class DeliveryGateRepository(MySQLRepository[DeliveryGateModel]):
    table = DeliveryGateTable

    async def acquire(
        self, channel_id: int, job_id: int, now: datetime
    ) -> bool:
        await self.upsert(
            DeliveryGateModel(channel_id=channel_id),
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.channel_id) == channel_id,
                col(self.table.job_id).is_(None)
                | (col(self.table.expires_at) <= now),
            )
            .values(job_id=job_id, expires_at=now + timedelta(seconds=60))
        )
        return cast(CursorResult, result).rowcount == 1

    async def release(self, channel_id: int, job_id: int) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.channel_id) == channel_id,
                col(self.table.job_id) == job_id,
            )
            .values(job_id=None, expires_at=None)
        )
