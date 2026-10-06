from dishka import Provider, Scope, provide

from her_api.modules.ops.commands.app.administration import (
    AdministrationCommands,
)
from her_api.modules.ops.commands.app.archive import ArchiveCommands
from her_api.modules.ops.commands.app.messages import MessageHandler
from her_api.modules.ops.commands.app.publishing import PublishingCommands
from her_api.modules.ops.commands.interfaces import (
    IAdministrationCommands,
    IArchiveCommands,
    IPublishingCommands,
)
from her_api.modules.ops.inbox.interfaces import IMessageHandler


class CommandsProvider(Provider):
    scope = Scope.REQUEST
    administration = provide(
        AdministrationCommands, provides=IAdministrationCommands
    )
    archive = provide(ArchiveCommands, provides=IArchiveCommands)
    publishing = provide(PublishingCommands, provides=IPublishingCommands)
    messages = provide(MessageHandler, provides=IMessageHandler)
