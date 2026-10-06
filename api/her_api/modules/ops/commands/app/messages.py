import json
import re

from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.transaction import transaction

from her_api.modules.content.channel.interfaces import IChannelCommands
from her_api.modules.conversations.actions.app.capabilities import (
    OwnerCapabilities,
)
from her_api.modules.conversations.actions.interfaces import IOwnerActions
from her_api.modules.conversations.chat.interfaces import IChatCommands
from her_api.modules.library.tracks.interfaces import ITrackService
from her_api.modules.ops.commands.interfaces import (
    IAdministrationCommands,
    IArchiveCommands,
    IPublishingCommands,
)
from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.persona.privacy.app.guard import normalize
from her_api.modules.publishing.deliveries.domain.models import (
    PublicationJobModel,
)
from her_api.modules.publishing.deliveries.infra.mysql import (
    PublicationRepository,
)
from her_api.shared.dates import utc_now
from her_contracts.channel import ChannelPostWrite
from her_contracts.commands import CommandResult
from her_contracts.telegram import IncomingMessage


class MessageHandler:
    def __init__(
        self,
        settings: ISettingsQueries,
        channel: IChannelCommands,
        chat: IChatCommands,
        tracks: ITrackService,
        actions: IOwnerActions,
        archive: IArchiveCommands,
        administration: IAdministrationCommands,
        publishing: IPublishingCommands,
        replies: PublicationRepository,
    ):
        self.capabilities = OwnerCapabilities()
        (
            self.settings,
            self.channel,
            self.chat,
            self.tracks,
            self.actions,
            self.archive,
            self.administration,
            self.publishing,
            self.replies,
        ) = (
            settings,
            channel,
            chat,
            tracks,
            actions,
            archive,
            administration,
            publishing,
            replies,
        )

    async def handle(self, data: IncomingMessage) -> None:
        settings = await self.settings.snapshot()
        access = settings.access
        if data.channel_post:
            await self.channel.observe(
                ChannelPostWrite(
                    channel_id=data.chat_id,
                    message_id=data.message_id,
                    text=data.text,
                    posted_at=data.posted_at,
                    edited_at=data.edited_at,
                    media_kind="audio" if data.audio else "text",
                )
            )
            return
        if (
            data.sender_id is None
            or data.sender_chat_id is not None
            or data.sender_is_bot
        ):
            return
        owner = data.sender_id == access.owner_id
        private = (
            data.chat_type == "private"
            and data.chat_id == access.owner_id
            and owner
        )
        group = (
            data.chat_type in {"group", "supergroup"}
            and data.chat_id == access.group_id
        )
        if not private and not (group and (owner or access.group_enabled)):
            return
        if private and data.forwarded_post is not None:
            if data.forwarded_post.channel_id != access.channel_id:
                await self._reply(
                    data,
                    CommandResult(
                        text=(
                            "فقط پیام فورواردشده از کانال خودمون رو وارد "
                            "تاریخچه می‌کنم 🕯️"
                        )
                    ),
                )
                return
            await self.channel.observe(data.forwarded_post)
            await self._reply(
                data,
                CommandResult(
                    text="این پیام به تاریخچهٔ مشاهده‌شدهٔ کانال اضافه شد 🕯️"
                ),
            )
            return
        if data.audio:
            if private:
                track = await self.tracks.upload(data.audio)
                await self._reply(
                    data,
                    CommandResult(
                        text="آهنگ ذخیره شد 🎧\nشناسه: " + str(track.id)
                    ),
                )
            return
        text = normalize(data.text).strip()
        first, _, args = data.text.strip().partition(" ")
        command = (
            normalize(first.removeprefix("/").split("@", 1)[0])
            if first.startswith("/")
            else ""
        )
        if command in {"start", "about", "back"}:
            await self._reply(
                data,
                CommandResult(
                    text="من " + settings.persona.display_name + "م 🎀🍓\n"
                    "یه شخصیت مجازی‌ام؛ می‌تو"
                    "نیم حرف بزنیم یا آرشیو آهنگ رو برای کانا"
                    "ل آماده کنیم.\n\n🕯️ /status · /plan\n🎧 /tra"
                    "cks · /preview ID\n✍️ /draft · /publish\n⏸"
                    " /pause · /resume\n🧹 /forget",
                    private=False,
                ),
            )
            return
        if command == "forget":
            await self.chat.forget(data.chat_id, data.sender_id)
            await self._reply(
                data,
                CommandResult(
                    text="تاریخچهٔ گفت‌وگوی خودت تو این چت پاک شد 🎀",
                    private=False,
                ),
            )
            return
        if command == "unsupported_media":
            await self._reply(
                data,
                CommandResult(
                    text="اینجا با متن حرف می‌زنیم 🎀\n"
                    "برای آرشیو، فایل Audio آهنگ رو بفرست.",
                    private=False,
                ),
            )
            return
        if command == "import_help" and private:
            await self._reply(
                data,
                CommandResult(
                    text=(
                        "اول /import_channel رو بزن؛ بعد JSON خروجی کانال "
                        "تا ۱۰MB رو بفرست. پیش‌نمایش می‌دم و با تأیید تو "
                        "ذخیره می‌کنم 🕯️"
                    )
                ),
            )
            return
        if command:
            if not owner:
                return
            try:
                result = await self.archive.handle(data, command, args)
                if result is None:
                    result = await self.administration.handle(
                        data, command, args
                    )
                if result is None:
                    result = await self.publishing.handle(data, command, args)
            except (ValueError, IndexError, NotFoundException):
                result = CommandResult(
                    text="ورودی این فرمان درست نیست یا دسترسی\u200cاش ف"
                    "راهم نشده. با /start برگرد 🎀"
                )
            if result is not None:
                await self._reply(data, result)
            return
        greeting = (
            owner
            and data.addressed
            and "greet_audience" in self.capabilities.allowed(data.text)
            and bool(
                re.search(
                    r"(به بچهها|به بچه ها|به همه).*سلام کن|"
                    r"خودت[و ]*معرفی کن|معرفی شو",
                    text,
                )
            )
        )
        if greeting:
            destination = (
                "discussion_group"
                if group or re.search(r"تو گروه|در گروه", text)
                else "channel"
            )
            await self.actions.execute(
                data.update_id,
                data.sender_id,
                "greet_audience",
                json.dumps(
                    {
                        "destination": destination,
                        "text": settings.persona.greeting_fallback,
                    },
                    ensure_ascii=False,
                ),
                frozenset({"greet_audience"}),
            )
            if private:
                await self._reply(
                    data,
                    CommandResult(
                        text="سلام در صف ارسال قرار گرفت 🎀\nوقتی تلگرام"
                        " تأیید کرد خبر می\u200cدم."
                    ),
                )
            return
        accepted = await self.chat.admit(data)
        if not accepted:
            await self._reply(
                data,
                CommandResult(
                    text="یه مکث کوچولو بده؛ چند ثانیه دیگه "
                    "دوباره حرف بزنیم 🎀",
                    private=False,
                ),
            )

    async def _reply(
        self, data: IncomingMessage, result: CommandResult
    ) -> None:
        settings = await self.settings.snapshot()
        target = settings.access.owner_id if result.private else data.chat_id
        now = utc_now()
        async with transaction():
            await self.replies.reply(
                PublicationJobModel(
                    kind="reply",
                    owner_id=settings.access.owner_id,
                    channel_id=target,
                    automatic=False,
                    update_id=data.update_id,
                    write_slot=2,
                    text=result.text[:4000],
                    target_message_id=data.message_id
                    if target == data.chat_id
                    else None,
                    scheduled_at=now,
                    next_attempt_at=now,
                )
            )
