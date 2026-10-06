from dishka import Provider, Scope, provide

from her_api.modules.content.channel.app.commands import ChannelCommands
from her_api.modules.content.channel.app.queries import ChannelQueries
from her_api.modules.content.channel.infra.mysql import (
    ChannelCoverageRepository,
    ChannelImportRepository,
    ChannelPostRepository,
    ImportSessionRepository,
)
from her_api.modules.content.channel.infra.readers import ChannelReader
from her_api.modules.content.channel.interfaces import (
    IChannelCommands,
    IChannelQueries,
)


class ChannelProvider(Provider):
    scope = Scope.REQUEST
    posts = provide(ChannelPostRepository)
    imports = provide(ChannelImportRepository)
    sessions = provide(ImportSessionRepository)
    coverage = provide(ChannelCoverageRepository)
    reader = provide(ChannelReader)
    commands = provide(ChannelCommands, provides=IChannelCommands)
    queries = provide(ChannelQueries, provides=IChannelQueries)
