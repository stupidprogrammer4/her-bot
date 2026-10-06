from dishka import Provider, Scope, provide

from her_api.modules.conversations.actions.app.commands import OwnerActions
from her_api.modules.conversations.actions.infra.mysql import (
    DeleteConfirmationRepository,
    OwnerActionRepository,
)
from her_api.modules.conversations.actions.interfaces import IOwnerActions


class OwnerActionsProvider(Provider):
    scope = Scope.REQUEST
    actions = provide(OwnerActionRepository)
    confirmations = provide(DeleteConfirmationRepository)
    commands = provide(OwnerActions, provides=IOwnerActions)
