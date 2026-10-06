from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.publishing.deliveries.infra.readers import (
    PublicationReader,
)
from her_api.modules.publishing.plans.app.sampling import WindowSampler
from her_api.modules.publishing.plans.domain.models import PlanModel
from her_api.modules.publishing.plans.infra.mysql import PlanRepository
from her_api.shared.clock import Clock
from her_contracts.publications import JobOut


class PlanQueries:
    def __init__(
        self,
        plans: PlanRepository,
        reader: PublicationReader,
        settings: ISettingsQueries,
        sampler: WindowSampler,
        clock: Clock,
    ):
        self.clock = clock
        self.plans, self.reader, self.settings, self.sampler = (
            plans,
            reader,
            settings,
            sampler,
        )

    async def current(self) -> tuple[PlanModel | None, list[JobOut]]:
        settings = await self.settings.snapshot()
        day, _, _, _ = self.sampler.evening(self.clock.now(), settings.window)
        plan = await self.plans.for_evening(settings.access.channel_id, day)
        rows = await self.reader.jobs(plan.id) if plan else []
        return plan, [
            JobOut.model_validate(r, from_attributes=True) for r in rows
        ]
