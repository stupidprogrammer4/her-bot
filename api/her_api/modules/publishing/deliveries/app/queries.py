from papilio.errors.exceptions import NotFoundException

from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.publishing.deliveries.infra.mysql import (
    PublicationRepository,
)
from her_contracts.publications import JobOut


class PublicationQueries:
    def __init__(
        self, repo: PublicationRepository, settings: ISettingsQueries
    ):
        self.repo, self.settings = repo, settings

    async def job(self, job_id: int) -> JobOut:
        row = await self.repo.get(job_id)
        if row is None:
            raise NotFoundException(
                "Publication not found",
                "record_not_found",
                "publication",
                "id",
                job_id,
            )
        return JobOut.model_validate(row, from_attributes=True)

    async def owned_post(self, message_id: int) -> JobOut:
        settings = await self.settings.snapshot()
        row = await self.repo.owned_post(
            settings.access.channel_id, message_id
        )
        if row is None:
            raise ValueError("Recorded own text post required")
        return JobOut.model_validate(row, from_attributes=True)

    async def recent(self, limit: int = 10) -> list[JobOut]:
        if not 1 <= limit <= 30:
            raise ValueError("Invalid limit")
        rows = await self.repo.recent(limit)
        return [
            JobOut.model_validate(row, from_attributes=True) for row in rows
        ]
