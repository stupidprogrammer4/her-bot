from collections.abc import Awaitable
from typing import Protocol

from her_contracts.commands import CommandResult
from her_contracts.telegram import IncomingMessage


class IArchiveCommands(Protocol):
    def handle(
        self, data: IncomingMessage, command: str, args: str
    ) -> Awaitable[CommandResult | None]: ...


class IAdministrationCommands(Protocol):
    def handle(
        self, data: IncomingMessage, command: str, args: str
    ) -> Awaitable[CommandResult | None]: ...


class IPublishingCommands(Protocol):
    def handle(
        self, data: IncomingMessage, command: str, args: str
    ) -> Awaitable[CommandResult | None]: ...
