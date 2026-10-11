from dishka import Provider, Scope, provide

from her_api.modules.content.occasions.app.queries import OccasionQueries
from her_api.modules.content.occasions.app.service import OccasionService
from her_api.modules.content.occasions.infra.mysql import OccasionRepository
from her_api.modules.content.occasions.interfaces import (
    IOccasionQueries,
    IOccasionService,
)


class OccasionProvider(Provider):
    scope = Scope.REQUEST
    repository = provide(OccasionRepository)
    service = provide(OccasionService, provides=IOccasionService)
    queries = provide(OccasionQueries, provides=IOccasionQueries)
