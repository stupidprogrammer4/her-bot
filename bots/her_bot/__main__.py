import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiohttp import web

from her_bot.app.acknowledgements import DurableAcknowledgements
from her_bot.app.delivery import Delivery
from her_bot.app.gateway import Gateway
from her_bot.app.heartbeat import PollingHeartbeat
from her_bot.app.updates import UpdateHandler
from her_bot.config.settings import BotSettings
from her_bot.infra.backend import Backend


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    settings = BotSettings.environment()
    bot = Bot(settings.token.get_secret_value())
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10, connect=5), trust_env=False
    ) as http:
        backend = Backend(http, settings)
        config = await backend.configuration()
        me = await bot.get_me()
        member = await bot.get_chat_member(config.channel_id, me.id)
        if member.status not in {"administrator", "creator"} or not getattr(
            member, "can_post_messages", False
        ):
            raise RuntimeError(
                "Channel administrator with posting permission required"
            )
        if config.group_id:
            group_member = await bot.get_chat_member(config.group_id, me.id)
            if group_member.status not in {
                "member",
                "administrator",
                "creator",
            }:
                raise RuntimeError("Discussion group membership required")
        await bot.set_my_name(config.display_name)
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="خانهٔ شمع زیبا 🎀"),
                BotCommand(command="about", description="دربارهٔ Her 🕯️"),
                BotCommand(
                    command="forget", description="پاک‌کردن تاریخچهٔ خودت 🧹"
                ),
            ]
        )
        acknowledgements = DurableAcknowledgements()
        bot.session.middleware(acknowledgements)
        bot.session.middleware(PollingHeartbeat(backend))
        handler = UpdateHandler(
            bot, backend, config, me.username or "", acknowledgements
        )
        dispatcher = Dispatcher()
        dispatcher.include_router(handler.router)
        gateway = Gateway(Delivery(bot, backend), settings)
        runner = web.AppRunner(gateway.app, access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, settings.host, settings.port).start()
            await bot.delete_webhook(drop_pending_updates=False)
            gateway.ready = True
            await dispatcher.start_polling(
                bot,
                handle_as_tasks=False,
                allowed_updates=[
                    "message",
                    "edited_message",
                    "channel_post",
                    "edited_channel_post",
                    "callback_query",
                    "my_chat_member",
                ],
                close_bot_session=False,
            )
        finally:
            gateway.ready = False
            await runner.cleanup()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
