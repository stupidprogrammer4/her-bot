from collections.abc import Awaitable
from typing import Protocol

from her_api.modules.publishing.plans.domain.models import PlanModel
from her_contracts.publications import JobOut


class IPlanCommands(Protocol):
    def prepare(self) -> Awaitable[PlanModel]: ...


class IPlanQueries(Protocol):
    def current(self) -> Awaitable[tuple[PlanModel | None, list[JobOut]]]: ...
