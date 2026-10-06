from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

from aiogram import Bot
from aiogram.methods import GetUpdates
from aiogram.methods.base import TelegramMethod

from her_bot.infra.backend import Backend, BackendUnavailable


class PollingHeartbeat:
    def __init__(self, backend: Backend):
        self.backend = backend
        self.next_at = 0.0

    async def __call__(
        self,
        make_request: Callable[[Bot, TelegramMethod[Any]], Awaitable[Any]],
        bot: Bot,
        method: TelegramMethod[Any],
    ) -> Any:
        if isinstance(method, GetUpdates) and monotonic() >= self.next_at:
            try:
                await self.backend.heartbeat()
            except BackendUnavailable:
                self.next_at = monotonic() + 10
            else:
                self.next_at = monotonic() + 60
        response = await make_request(bot, method)
        return response
