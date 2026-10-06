from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot
from aiogram.methods import GetUpdates
from aiogram.methods.base import TelegramMethod


class DurableAcknowledgements:
    """Clamp polling offsets to updates actually accepted by the backend."""

    def __init__(self):
        self.highest_committed = -1
        self.pending: set[int] = set()

    def committed(self, update_id: int) -> None:
        self.pending.discard(update_id)
        self.highest_committed = max(self.highest_committed, update_id)

    def failed(self, update_id: int) -> None:
        self.pending.add(update_id)

    async def __call__(
        self,
        make_request: Callable[[Bot, TelegramMethod[Any]], Awaitable[Any]],
        bot: Bot,
        method: TelegramMethod[Any],
    ) -> Any:
        if (
            isinstance(method, GetUpdates)
            and method.offset is not None
            and method.offset > 0
        ):
            durable_offset = (
                min(self.pending)
                if self.pending
                else self.highest_committed + 1
            )
            method = method.model_copy(
                update={"offset": min(method.offset, durable_offset)}
            )
        response = await make_request(bot, method)
        return response
