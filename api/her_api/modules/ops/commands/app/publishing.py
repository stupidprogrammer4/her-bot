from her_api.modules.ai.generation.domain.errors import ModelUnavailable
from her_api.modules.ai.generation.interfaces import IGenerationCommands
from her_api.modules.content.channel.interfaces import (
    IChannelCommands,
    IChannelQueries,
)
from her_api.modules.conversations.actions.interfaces import IOwnerActions
from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.publishing.deliveries.interfaces import (
    IPublicationCommands,
    IPublicationQueries,
)
from her_api.modules.publishing.plans.interfaces import IPlanQueries
from her_contracts.commands import CommandResult
from her_contracts.generation import GenerationRequest, ModelMessage
from her_contracts.publications import ManualPublication
from her_contracts.telegram import IncomingMessage


class PublishingCommands:
    def __init__(
        self,
        publications: IPublicationCommands,
        publication_queries: IPublicationQueries,
        plans: IPlanQueries,
        channel: IChannelQueries,
        content: IChannelCommands,
        settings: ISettingsQueries,
        generation: IGenerationCommands,
        actions: IOwnerActions,
    ):
        (
            self.publications,
            self.publication_queries,
            self.plans,
            self.channel,
            self.content,
            self.settings,
            self.generation,
            self.actions,
        ) = (
            publications,
            publication_queries,
            plans,
            channel,
            content,
            settings,
            generation,
            actions,
        )

    async def handle(
        self, data: IncomingMessage, command: str, args: str
    ) -> CommandResult | None:
        if command == "status":
            settings = await self.settings.snapshot()
            jobs = await self.publication_queries.recent()
            lines = [
                "🕯️ وضعیت Her",
                "نشر: " + ("متوقف" if settings.access.paused else "فعال"),
                "گفت‌وگوی گروه: "
                + ("فعال" if settings.access.group_enabled else "غیرفعال"),
            ]
            lines.extend(
                "کار " + str(j.id) + " · " + j.kind + " · " + j.status
                for j in jobs
            )
            return CommandResult(text="\n".join(lines))
        if command == "plan":
            plan, jobs = await self.plans.current()
            if plan is None:
                return CommandResult(
                    text="برنامه هنوز ساخته نشده؛ زمان‌بند آماده‌اش می‌کنه."
                )
            return CommandResult(
                text="🕯️ برنامهٔ "
                + str(plan.evening_date)
                + "\nموسیقی: "
                + plan.music_status
                + "\nمتن: "
                + str(plan.text_count)
                + "\n"
                + "\n".join(
                    str(j.id)
                    + " · "
                    + j.kind
                    + " · "
                    + j.scheduled_at.isoformat()
                    + " · "
                    + j.status
                    for j in jobs
                )
            )
        if command in {"publish", "play"}:
            if command == "publish":
                job = await self.publications.reserve(
                    ManualPublication(
                        update_id=data.update_id,
                        actor_id=data.sender_id or 0,
                        kind="text",
                        text=args,
                    )
                )
            else:
                track, *caption = args.split(maxsplit=1)
                job = await self.publications.reserve(
                    ManualPublication(
                        update_id=data.update_id,
                        actor_id=data.sender_id or 0,
                        kind="music",
                        track_id=int(track),
                        text=caption[0] if caption else None,
                    )
                )
            return CommandResult(
                text="در صف ارسال قرار گرفت 🎀\nکار: "
                + str(job.id)
                + "\nنتیجهٔ قطعی رو بعد از پاسخ تلگرام می‌گم."
            )
        if command == "draft":
            context = await self.channel.context()
            try:
                result = await self.generation.complete(
                    GenerationRequest(
                        mode="channel_post",
                        messages=[
                            ModelMessage(
                                role="user",
                                content="Write a Persian channel draft only. "
                                + args,
                            )
                        ],
                        data={
                            "public_context": [
                                p.model_dump(mode="json")
                                for p in context.posts
                            ]
                        },
                    )
                )
                return CommandResult(
                    text="پیش‌نویس؛ منتشر نشده:\n\n"
                    + (result.message.content or "")
                )
            except (ModelUnavailable, ValueError):
                return CommandResult(
                    text="الان پیش‌نویس ساخته نشد؛ چیزی منتشر نکردم."
                )
        if command == "resolve":
            parts = args.split()
            job_id = int(parts[0])
            if parts[1] not in {"sent", "skip"}:
                raise ValueError("Use sent or skip")
            await self.publications.resolve(
                job_id,
                data.sender_id or 0,
                int(parts[2]) if parts[1] == "sent" else None,
            )
            return CommandResult(
                text="وضعیت با تأیید خودت ثبت شد؛ محتوای پیام "
                "رو از تلگرام نخوندم."
            )
        if command == "retry":
            parts = args.split()
            text = await self.publications.retry(
                int(parts[0]),
                data.sender_id or 0,
                len(parts) == 2 and parts[1] == "confirm",
            )
            return CommandResult(text=text)
        if command == "delete_confirm":
            result = await self.actions.confirm_delete(
                data.update_id, data.sender_id or 0, args
            )
            return CommandResult(
                text="درخواست حذف ثبت شد؛ نتیجه را بعد از پاسخ تلگرام می‌گم.\n"
                + result
            )
        if command == "channel_context":
            if data.chat_type != "private":
                return CommandResult(text="جزئیات کانال رو تو خصوصی بگیر.")
            context = await self.channel.context()
            return CommandResult(
                text="پوشش ذخیره‌شده؛ تاریخچهٔ کامل تلگرام نیست.\n"
                + context.model_dump_json(indent=2)
            )
        if command == "import_channel":
            if data.chat_type != "private":
                return CommandResult(text="ورود تاریخچه فقط تو خصوصی فعاله.")
            await self.content.start_import(data.sender_id or 0)
            return CommandResult(
                text="فایل JSON خروجی کانال رو بفرست؛ اول پیش\u200c"
                "نمایش می\u200cدم، بعد با تأییدت ذخیره می\u200cکنم."
                " حداکثر ۱۰MB. هیچ فایلی دانلود یا منتشر "
                "نمی\u200cشه."
            )
        if command == "import_confirm":
            if data.chat_type != "private":
                raise ValueError("Private import required")
            token, *options = args.split()
            count = await self.content.import_confirm(
                token, data.sender_id or 0, options == ["map"]
            )
            return CommandResult(
                text=str(count) + " پیام برای زمینه ذخیره شد؛ پستی منتشر نشد."
            )
        if command == "context_remove":
            if data.chat_type != "private":
                raise ValueError("Private context management required")
            await self.content.deactivate(int(args))
            return CommandResult(text="از زمینه حذف شد؛ پیام تلگرام پاک نشده.")
        return None
