from dishka import Provider, Scope, provide

from her_api.modules.conversations.chat.app.commands import ChatCommands
from her_api.modules.conversations.chat.infra.mysql import (
    ChatRequestRepository,
    ConversationPairRepository,
    ConversationRepository,
)
from her_api.modules.conversations.chat.infra.readers import ConversationReader
from her_api.modules.conversations.chat.interfaces import IChatCommands
from her_api.modules.conversations.chat.tasks.schedulers.converse import (
    Converse,
)


class ChatProvider(Provider):
    scope = Scope.REQUEST
    requests = provide(ChatRequestRepository)
    conversations = provide(ConversationRepository)
    pairs = provide(ConversationPairRepository)
    reader = provide(ConversationReader)
    commands = provide(ChatCommands, provides=IChatCommands)
    converse = provide(Converse)
