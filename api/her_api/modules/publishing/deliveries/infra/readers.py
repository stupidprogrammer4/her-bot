from datetime import date

from papilio.infra.db.repositories.backends.mysql import MySQLReader
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from sqlmodel import col

from her_api.modules.library.tracks.domain.dtos import TrackCandidate
from her_api.modules.library.tracks.infra.tables import TrackTable
from her_api.modules.publishing.deliveries.domain.dtos import (
    UnnotifiedPublication,
)
from her_api.modules.publishing.deliveries.infra.tables import (
    PublicationJobTable,
)
from her_api.modules.publishing.plans.infra.tables import PlanTable


class PublicationReader(MySQLReader):
    async def unnotified_failures(
        self, limit: int = 30
    ) -> list[UnnotifiedPublication]:
        job = PublicationJobTable
        notification = aliased(PublicationJobTable)
        result = await self.uow.execute(
            select(job)
            .outerjoin(
                notification, col(notification.parent_job_id) == col(job.id)
            )
            .where(
                col(job.kind) != "reply",
                col(job.status).in_(["failed", "delivery_unknown"]),
                col(notification.id).is_(None),
            )
            .order_by(col(job.id))
            .limit(limit)
        )
        return [UnnotifiedPublication(job=row) for row in result.scalars()]

    async def track_candidates(self, channel_id: int) -> list[TrackCandidate]:
        t, j = TrackTable, PublicationJobTable
        played = (
            select(
                col(j.track_id).label("track_id"),
                func.max(col(j.sent_at)).label("last_played"),
            )
            .where(
                col(j.status) == "sent",
                col(j.kind) == "music",
                col(j.channel_id) == channel_id,
            )
            .group_by(col(j.track_id))
            .subquery()
        )
        result = await self.uow.execute(
            select(t, played.c.last_played)
            .outerjoin(played, col(t.id) == played.c.track_id)
            .where(col(t.active).is_(True))
        )
        return [
            TrackCandidate(track=t, last_played=stamp) for t, stamp in result
        ]

    async def jobs(self, plan_id: int) -> list[PublicationJobTable]:
        j = PublicationJobTable
        result = await self.uow.execute(
            select(j)
            .where(col(j.plan_id) == plan_id)
            .order_by(col(j.scheduled_at), col(j.id))
        )
        return list(result.scalars())

    async def previous_topics(self, channel_id: int, day: date) -> set[str]:
        j, p = PublicationJobTable, PlanTable
        latest = (
            select(func.max(col(p.evening_date)))
            .where(col(p.channel_id) == channel_id, col(p.evening_date) < day)
            .scalar_subquery()
        )
        result = await self.uow.execute(
            select(col(j.topic))
            .join(p, col(j.plan_id) == col(p.id))
            .where(
                col(p.channel_id) == channel_id,
                col(p.evening_date) == latest,
                col(j.kind) == "text",
            )
            .order_by(col(p.evening_date).desc())
            .limit(10)
        )
        return {t for t in result.scalars() if t}

    async def recent_texts(
        self, channel_id: int, limit: int = 10
    ) -> list[str]:
        j = PublicationJobTable
        result = await self.uow.execute(
            select(col(j.text))
            .where(
                col(j.channel_id) == channel_id,
                col(j.status).in_(["pending", "preparing", "sent"]),
                col(j.text).is_not(None),
            )
            .order_by(
                func.coalesce(col(j.sent_at), col(j.created_at)).desc(),
                col(j.id).desc(),
            )
            .limit(limit)
        )
        return [text for text in result.scalars() if text]
