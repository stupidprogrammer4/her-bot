from collections.abc import Awaitable
from typing import Protocol

from her_contracts.channel import (
    ChannelContext,
    ChannelPostWrite,
    ImportPreview,
)


class IChannelCommands(Protocol):
    def start_import(self, actor_id: int) -> Awaitable[None]: ...
    def import_open(self, actor_id: int) -> Awaitable[bool]: ...
    def heartbeat(self) -> Awaitable[None]: ...
    def observe(self, post: ChannelPostWrite) -> Awaitable[None]: ...
    def import_preview(
        self,
        raw: str,
        actor_id: int,
        update_id: int | None = None,
        message_id: int | None = None,
    ) -> Awaitable[ImportPreview]: ...
    def import_confirm(
        self, token: str, actor_id: int, explicit_mapping: bool = False
    ) -> Awaitable[int]: ...
    def deactivate(self, message_id: int) -> Awaitable[None]: ...
    def purge(self) -> Awaitable[None]: ...


class IChannelQueries(Protocol):
    def context(
        self, limit: int | None = None, query: str | None = None
    ) -> Awaitable[ChannelContext]: ...
