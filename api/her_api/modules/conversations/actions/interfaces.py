from collections.abc import Awaitable
from typing import Protocol


class IOwnerActions(Protocol):
    def execute(
        self,
        update_id: int,
        actor_id: int,
        name: str,
        arguments: str,
        allowed: frozenset[str],
    ) -> Awaitable[str]: ...
    def confirm_delete(
        self, update_id: int, actor_id: int, token: str
    ) -> Awaitable[str]: ...
