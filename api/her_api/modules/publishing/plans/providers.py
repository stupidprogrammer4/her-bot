from random import SystemRandom

from dishka import Provider, Scope, provide

from her_api.modules.publishing.plans.app.commands import PlanCommands
from her_api.modules.publishing.plans.app.queries import PlanQueries
from her_api.modules.publishing.plans.app.sampling import WindowSampler
from her_api.modules.publishing.plans.infra.mysql import PlanRepository
from her_api.modules.publishing.plans.interfaces import (
    IPlanCommands,
    IPlanQueries,
)


class PlanningProvider(Provider):
    scope = Scope.REQUEST
    repo = provide(PlanRepository)
    sampler = provide(WindowSampler)
    commands = provide(PlanCommands, provides=IPlanCommands)
    queries = provide(PlanQueries, provides=IPlanQueries)

    @provide(scope=Scope.APP)
    def randomness(self) -> SystemRandom:
        return SystemRandom()
