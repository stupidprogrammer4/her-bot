from dishka import Provider, Scope, provide

from her_api.modules.ops.inbox.app.commands import InboxCommands
from her_api.modules.ops.inbox.infra.mysql import InboxRepository
from her_api.modules.ops.inbox.interfaces import IInboxCommands
from her_api.modules.ops.inbox.tasks.schedulers.process import ProcessUpdate
from her_api.modules.ops.inbox.tasks.schedulers.recover import RecoverWork
from her_api.modules.ops.inbox.tasks.schedulers.retention import ApplyRetention


class InboxProvider(Provider):
    scope = Scope.REQUEST
    repo = provide(InboxRepository)
    commands = provide(InboxCommands, provides=IInboxCommands)
    process = provide(ProcessUpdate)
    recover = provide(RecoverWork)
    retention = provide(ApplyRetention)
