import io
import re
from collections.abc import Buffer
from datetime import UTC, datetime

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, Message, MessageOriginChannel, Update
from pydantic import TypeAdapter

from her_bot.app.acknowledgements import DurableAcknowledgements
from her_bot.app.addressing import Addressing
from her_bot.infra.backend import Backend, BackendUnavailable
from her_contracts.channel import ChannelPostWrite
from her_contracts.media import AudioUpload, Mood
from her_contracts.telegram import BotConfiguration, ChatType, IncomingMessage


class UpdateHandler:
    def __init__(
        self,
        bot: Bot,
        backend: Backend,
        configuration: BotConfiguration,
        username: str,
        acknowledgements: DurableAcknowledgements,
    ):
        self.bot, self.backend, self.configuration, self.acknowledgements = (
            bot,
            backend,
            configuration,
            acknowledgements,
        )
        self.addressing = Addressing(configuration.aliases, username)
        self.username = username.casefold()
        self.router = Router(name="her_updates")
        self.router.message.register(self.message)
        self.router.edited_message.register(self.message)
        self.router.channel_post.register(self.channel)
        self.router.edited_channel_post.register(self.channel)
        self.router.callback_query.register(self.callback)
        self.router.my_chat_member.register(self.membership)

    def envelope(
        self,
        message: Message,
        update_id: int,
        *,
        text: str | None = None,
        channel: bool = False,
    ) -> IncomingMessage:
        audio = None
        if message.audio:
            source = message.audio
            mood, tags = "neutral", []
            caption = message.caption or ""
            match = re.fullmatch(
                r"\s*mood=(calm|sad|romantic|energetic|nostalgic|neutral)(?:,tags=([^\n]*))?\s*",
                caption,
            )
            if match:
                mood = match.group(1)
                tags = [
                    t.strip()[:60]
                    for t in (match.group(2) or "").split(",")
                    if t.strip()
                ][:20]
            audio = AudioUpload(
                bot_id=self.bot.id,
                file_id=source.file_id,
                file_unique_id=source.file_unique_id,
                source_chat_id=message.chat.id,
                source_message_id=message.message_id,
                title=source.title or "",
                performer=source.performer or "",
                filename=source.file_name or "",
                duration=source.duration,
                file_size=source.file_size,
                mood=TypeAdapter(Mood).validate_python(mood),
                tags=tags,
            )
        content = (
            text if text is not None else message.text or message.caption or ""
        )
        addressed = (
            message.chat.type == "private"
            or self.addressing.addressed(
                content,
                replying_to_bot=bool(
                    message.reply_to_message
                    and message.reply_to_message.from_user
                    and message.reply_to_message.from_user.id == self.bot.id
                ),
            )
        )
        return IncomingMessage(
            update_id=update_id,
            message_id=message.message_id,
            chat_id=message.chat.id,
            chat_type=TypeAdapter(ChatType).validate_python(message.chat.type),
            sender_id=message.from_user.id if message.from_user else None,
            sender_is_bot=bool(message.from_user and message.from_user.is_bot),
            sender_chat_id=message.sender_chat.id
            if message.sender_chat
            else None,
            text=content,
            addressed=addressed,
            audio=audio,
            channel_post=channel,
            posted_at=message.date,
            edited_at=datetime.fromtimestamp(message.edit_date, UTC)
            if message.edit_date
            else None,
            forwarded_post=ChannelPostWrite(
                channel_id=message.forward_origin.chat.id,
                message_id=message.forward_origin.message_id,
                posted_at=message.forward_origin.date,
                text=message.text or "",
                caption=message.caption or "",
                media_kind="audio" if message.audio else "text",
                origin="imported",
            )
            if isinstance(message.forward_origin, MessageOriginChannel)
            else None,
        )

    async def message(self, message: Message, event_update: Update) -> None:
        first = (message.text or "").split(" ", 1)[0]
        if (
            first.startswith("/")
            and "@" in first
            and first.split("@", 1)[1].casefold() != self.username
        ):
            self.acknowledgements.committed(event_update.update_id)
            return
        try:
            self.configuration = await self.backend.configuration()
        except BackendUnavailable:
            self.acknowledgements.failed(event_update.update_id)
            return
        self.addressing.aliases = self.configuration.aliases
        if (
            message.document
            and message.chat.type == "private"
            and message.from_user
            and message.from_user.id == self.configuration.owner_id
        ):
            try:
                opened = await self.backend.import_open(message.from_user.id)
            except BackendUnavailable:
                self.acknowledgements.failed(event_update.update_id)
                return
            if opened:
                await self._import(message, event_update.update_id)
            else:
                await self._admit(
                    self.envelope(
                        message, event_update.update_id, text="/import_help"
                    )
                )
            return
        if not (
            message.text
            or message.audio
            or isinstance(message.forward_origin, MessageOriginChannel)
        ):
            await self._admit(
                self.envelope(
                    message, event_update.update_id, text="/unsupported_media"
                )
            )
            return
        data = self.envelope(message, event_update.update_id)
        await self._admit(data)

    async def channel(self, message: Message, event_update: Update) -> None:
        data = self.envelope(message, event_update.update_id, channel=True)
        await self._admit(data)

    async def callback(
        self, callback: CallbackQuery, event_update: Update
    ) -> None:
        try:
            await callback.answer()
        except TelegramAPIError:
            pass
        if not isinstance(callback.message, Message) or callback.data not in {
            "start",
            "about",
            "forget",
            "tracks",
            "plan",
            "status",
            "pause",
            "resume",
        }:
            self.acknowledgements.committed(event_update.update_id)
            return
        data = self.envelope(
            callback.message, event_update.update_id, text="/" + callback.data
        ).model_copy(
            update={
                "sender_id": callback.from_user.id,
                "sender_is_bot": callback.from_user.is_bot,
                "sender_chat_id": None,
                "audio": None,
                "callback_query_id": callback.id,
            }
        )
        await self._admit(data)

    async def membership(self, event_update: Update) -> None:
        self.acknowledgements.committed(event_update.update_id)

    async def _admit(self, data: IncomingMessage) -> None:
        try:
            await self.backend.admit(data)
        except BackendUnavailable:
            self.acknowledgements.failed(data.update_id)
            return
        self.acknowledgements.committed(data.update_id)

    async def _import(self, message: Message, update_id: int) -> None:
        document = message.document
        if (
            document is None
            or (document.file_size or 0) > 10 * 1024 * 1024
            or not (document.file_name or "").lower().endswith(".json")
        ):
            await message.answer(
                "فقط JSON تا ۱۰MB رو برای پیش‌نمایش می‌پذیرم.", parse_mode=None
            )
            self.acknowledgements.committed(update_id)
            return
        try:
            stream = await self.bot.download(
                document.file_id, destination=ImportBuffer()
            )
            if (
                not isinstance(stream, io.BytesIO)
                or stream.getbuffer().nbytes > 10 * 1024 * 1024
            ):
                raise ValueError("Invalid export")
            raw = stream.getvalue().decode("utf-8-sig")
            await self.backend.import_preview(
                raw,
                message.from_user.id if message.from_user else 0,
                message.chat.id,
                update_id,
                message.message_id,
            )
        except (ValueError, TelegramBadRequest):
            await message.answer(
                "فایل قابل خواندن نیست؛ JSON خروجی کانال رو دوباره بفرست.",
                parse_mode=None,
            )
            self.acknowledgements.committed(update_id)
            return
        except (BackendUnavailable, TelegramAPIError):
            self.acknowledgements.failed(update_id)
            return
        self.acknowledgements.committed(update_id)


class ImportBuffer(io.BytesIO):
    def write(self, data: Buffer) -> int:
        if self.tell() + memoryview(data).nbytes > 10 * 1024 * 1024:
            raise ValueError("Export exceeds size limit")
        return super().write(data)
