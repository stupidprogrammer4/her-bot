from dishka import Provider, Scope, provide

from her_api.modules.publishing.deliveries.app.commands import (
    PublicationCommands,
)
from her_api.modules.publishing.deliveries.app.content import (
    PublicationContent,
)
from her_api.modules.publishing.deliveries.app.preparation import (
    PublicationPreparation,
)
from her_api.modules.publishing.deliveries.app.queries import (
    PublicationQueries,
)
from her_api.modules.publishing.deliveries.infra.mysql import (
    DeliveryGateRepository,
    PublicationRepository,
)
from her_api.modules.publishing.deliveries.infra.readers import (
    PublicationReader,
)
from her_api.modules.publishing.deliveries.infra.telegram import (
    TelegramTransport,
)
from her_api.modules.publishing.deliveries.interfaces import (
    IPublicationCommands,
    IPublicationPreparation,
    IPublicationQueries,
    ITelegramTransport,
)
from her_api.modules.publishing.deliveries.tasks.schedulers.deliver import (
    Deliver,
)
from her_api.modules.publishing.deliveries.tasks.schedulers.prepare import (
    PreparePublication,
)


class PublicationProvider(Provider):
    scope = Scope.REQUEST
    jobs = provide(PublicationRepository)
    gates = provide(DeliveryGateRepository)
    reader = provide(PublicationReader)
    content = provide(PublicationContent)
    transport = provide(TelegramTransport, provides=ITelegramTransport)
    commands = provide(PublicationCommands, provides=IPublicationCommands)
    queries = provide(PublicationQueries, provides=IPublicationQueries)
    deliver = provide(Deliver)
    preparation = provide(
        PublicationPreparation, provides=IPublicationPreparation
    )
    prepare = provide(PreparePublication)
