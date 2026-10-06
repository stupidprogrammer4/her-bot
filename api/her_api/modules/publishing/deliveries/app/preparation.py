from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.transaction import transaction

from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.publishing.deliveries.app.content import (
    PublicationContent,
)
from her_api.modules.publishing.deliveries.domain.dtos import JobChange
from her_api.modules.publishing.deliveries.domain.models import (
    PublicationJobModel,
)
from her_api.modules.publishing.deliveries.infra.mysql import (
    PublicationRepository,
)
from her_api.shared.clock import Clock


class PublicationPreparation:
    def __init__(
        self,
        jobs: PublicationRepository,
        content: PublicationContent,
        settings: ISettingsQueries,
        clock: Clock,
    ):
        self.jobs = jobs
        self.content = content
        self.settings = settings
        self.clock = clock

    async def pending(self) -> list[int]:
        settings = await self.settings.snapshot()
        ids = await self.jobs.preparation_ids(
            self.clock.now(), include_automatic=not settings.access.paused
        )
        return ids

    async def prepare(self, job_id: int) -> None:
        settings = await self.settings.snapshot()
        async with transaction():
            claimed = await self.jobs.claim_generation(
                job_id,
                self.clock.now(),
                include_automatic=not settings.access.paused,
            )
        if not claimed:
            return
        row = await self.jobs.get(job_id)
        if row is None or row.preparing_started_at is None:
            raise ValueError("Preparation reservation missing")
        started_at = row.preparing_started_at
        job = PublicationJobModel.model_validate(row.model_dump())
        try:
            text = await self.content.prepare(job, settings)
            change = JobChange(
                status="pending", text=text, lease_expires_at=None
            )
        except (ValueError, RuntimeError, NotFoundException):
            change = JobChange(
                status="failed",
                failure_reason="safe_content_unavailable",
                lease_expires_at=None,
            )
        async with transaction():
            await self.jobs.finish_generation(job_id, started_at, change)
