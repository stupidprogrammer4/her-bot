from hmac import compare_digest

from aiohttp import web
from pydantic import ValidationError

from her_bot.app.delivery import Delivery
from her_bot.config.settings import BotSettings
from her_contracts.publications import TelegramSend


class Gateway:
    def __init__(self, delivery: Delivery, settings: BotSettings):
        self.delivery, self.settings = delivery, settings
        self.app = web.Application(client_max_size=32768)
        self.app.router.add_post("/internal/send", self.send)
        self.app.router.add_get("/health", self.health)
        self.ready = False

    async def send(self, request: web.Request) -> web.Response:
        expected = "Bearer " + self.settings.service_key.get_secret_value()
        if not compare_digest(
            request.headers.get("Authorization", "").encode(),
            expected.encode(),
        ):
            raise web.HTTPUnauthorized()
        if not self.ready:
            return web.json_response(
                {"status": "failed", "reason": "telegram_not_ready"}
            )
        try:
            data = TelegramSend.model_validate(await request.json())
        except (ValidationError, ValueError):
            raise web.HTTPBadRequest(text="Invalid send request") from None
        receipt = await self.delivery.send(data)
        return web.json_response(receipt.model_dump())

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response(
            {"status": "ok" if self.ready else "starting"},
            status=200 if self.ready else 503,
        )
