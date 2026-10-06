import asyncio
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import Message, ReplyParameters

from her_bot.app.menu import Menu
from her_bot.infra.backend import Backend
from her_contracts.publications import Receipt, TelegramSend


class Delivery:
    def __init__(self, bot: Bot, backend: Backend):
        self.bot, self.backend = bot, backend
        self.menu = Menu()

    async def send(self, data: TelegramSend) -> Receipt:
        configuration = await self.backend.configuration()
        if data.chat_id not in {
            configuration.owner_id,
            configuration.channel_id,
            configuration.group_id,
        }:
            return Receipt(status="failed", reason="destination_denied")
        remaining = (
            (data.deadline_at - datetime.now(UTC)).total_seconds()
            if data.deadline_at
            else 25
        )
        if remaining <= 0:
            return Receipt(status="failed", reason="publication_deadline")
        if (
            data.source_bot_id is not None
            and data.source_bot_id != self.bot.id
        ):
            return Receipt(status="failed", reason="audio_bot_mismatch")
        reply = (
            ReplyParameters(
                message_id=data.reply_to, allow_sending_without_reply=True
            )
            if data.reply_to
            else None
        )
        try:
            async with asyncio.timeout(min(25, remaining)):
                if data.kind in {"music", "preview"}:
                    if not data.file_id:
                        return Receipt(
                            status="failed", reason="missing_file_id"
                        )
                    message = await self.bot.send_audio(
                        data.chat_id,
                        data.file_id,
                        caption=data.text,
                        parse_mode=None,
                        reply_parameters=reply,
                    )
                    result = message.message_id
                elif data.kind == "edit":
                    if data.target_message_id is None:
                        return Receipt(
                            status="failed", reason="missing_message_id"
                        )
                    edited = await self.bot.edit_message_text(
                        data.text,
                        chat_id=data.chat_id,
                        message_id=data.target_message_id,
                        parse_mode=None,
                    )
                    result = (
                        edited.message_id
                        if isinstance(edited, Message)
                        else data.target_message_id
                    )
                elif data.kind == "delete":
                    if data.target_message_id is None:
                        return Receipt(
                            status="failed", reason="missing_message_id"
                        )
                    await self.bot.delete_message(
                        data.chat_id, data.target_message_id
                    )
                    result = data.target_message_id
                else:
                    keyboard = (
                        self.menu.keyboard(
                            data.chat_id == configuration.owner_id
                        )
                        if data.kind == "reply" and data.chat_id > 0
                        else None
                    )
                    message = await self.bot.send_message(
                        data.chat_id,
                        data.text,
                        parse_mode=None,
                        reply_parameters=reply,
                        reply_markup=keyboard,
                    )
                    result = message.message_id
        except TelegramRetryAfter as error:
            return Receipt(
                status="rate_limited", retry_after=error.retry_after
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            return Receipt(status="failed", reason="telegram_permanent_error")
        except (TelegramAPIError, TimeoutError, OSError):
            return Receipt(
                status="delivery_unknown", reason="telegram_response_unknown"
            )
        return Receipt(status="sent", message_id=result)
