from datetime import timedelta

from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.transaction import transaction

from her_api.modules.content.channel.interfaces import IChannelCommands
from her_api.modules.library.tracks.interfaces import ITrackService
from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.persona.privacy.app.guard import IdentityGuard
from her_api.modules.publishing.deliveries.app.content import (
    PublicationContent,
)
from her_api.modules.publishing.deliveries.domain.dtos import JobChange
from her_api.modules.publishing.deliveries.domain.models import (
    PublicationJobModel,
)
from her_api.modules.publishing.deliveries.infra.mysql import (
    DeliveryGateRepository,
    PublicationRepository,
)
from her_api.modules.publishing.deliveries.infra.readers import (
    PublicationReader,
)
from her_api.modules.publishing.deliveries.interfaces import ITelegramTransport
from her_api.shared.clock import Clock
from her_api.shared.dates import as_utc
from her_contracts.channel import ChannelPostWrite
from her_contracts.publications import (
    JobOut,
    ManualPublication,
    Receipt,
    TelegramSend,
)


class PublicationCommands:
    def __init__(
        self,
        jobs: PublicationRepository,
        gates: DeliveryGateRepository,
        settings: ISettingsQueries,
        tracks: ITrackService,
        content: PublicationContent,
        telegram: ITelegramTransport,
        channel: IChannelCommands,
        guard: IdentityGuard,
        clock: Clock,
        reader: PublicationReader,
    ):
        self.clock = clock
        self.reader = reader
        (
            self.jobs,
            self.gates,
            self.settings,
            self.tracks,
            self.content,
            self.telegram,
            self.channel,
            self.guard,
        ) = jobs, gates, settings, tracks, content, telegram, channel, guard

    async def reserve(self, data: ManualPublication) -> JobOut:
        settings = await self.settings.snapshot()
        if data.actor_id != settings.access.owner_id:
            raise ValueError("Owner required")
        targets = {
            "channel": settings.access.channel_id,
            "discussion_group": settings.access.group_id,
            "owner": settings.access.owner_id,
        }
        target = targets[data.destination]
        if target is None:
            raise ValueError("Destination not configured")
        if data.kind == "reply" or (
            data.kind == "preview" and data.destination != "owner"
        ):
            raise ValueError("Invalid manual publication")
        if data.text is not None:
            self.guard.require_safe(data.text)
            if not data.text.strip() or len(data.text) > (
                500
                if data.kind in {"music", "preview"}
                else 400
                if data.kind == "greeting"
                else 700
            ):
                raise ValueError("Invalid text")
        if data.kind in {"music", "preview"}:
            if data.track_id is None:
                raise ValueError("Track required")
            track = await self.tracks.get(data.track_id)
            if not track.active:
                raise ValueError("Track disabled")
        if data.kind in {"edit", "delete"}:
            owned = await self.jobs.owned_post(
                target, data.target_message_id or 0
            )
            if owned is None:
                raise ValueError("Recorded own post required")
        now = self.clock.now()
        async with transaction():
            existing = await self.jobs.for_update(data.update_id)
            if existing is not None:
                return JobOut.model_validate(existing, from_attributes=True)
            row = await self.jobs.reserve(
                PublicationJobModel(
                    kind=data.kind,
                    channel_id=target,
                    owner_id=data.actor_id,
                    automatic=False,
                    update_id=data.update_id,
                    write_slot=1,
                    text=data.text,
                    track_id=data.track_id,
                    target_message_id=data.target_message_id,
                    scheduled_at=now,
                    next_attempt_at=now,
                )
            )
        return JobOut.model_validate(row, from_attributes=True)

    async def deliver(self, job_id: int) -> None:
        now = self.clock.now()
        settings = await self.settings.snapshot()
        async with transaction():
            claimed = await self.jobs.claim_preparing(
                job_id, now, settings.window.prepare_seconds
            )
        if not claimed:
            return
        job = await self.jobs.get(job_id)
        if job is None:
            raise ValueError("Publication not found")
        settings = await self.settings.snapshot()
        if job.automatic and settings.access.paused:
            async with transaction():
                await self.jobs.change(
                    job_id,
                    JobChange(
                        status="pending",
                        next_attempt_at=now + timedelta(seconds=2),
                        lease_expires_at=None,
                    ),
                    expected="preparing",
                )
            return
        if job.deadline_at and now >= as_utc(job.deadline_at):
            async with transaction():
                await self.jobs.change(
                    job_id, JobChange(status="expired"), expected="preparing"
                )
            return
        try:
            text = (
                ""
                if job.kind == "delete"
                else await self.content.prepare(job, settings)
            )
        except (ValueError, RuntimeError, NotFoundException):
            async with transaction():
                await self.jobs.change(
                    job_id,
                    JobChange(
                        status="failed",
                        failure_reason="safe_content_unavailable",
                    ),
                    expected="preparing",
                )
            return
        now = self.clock.now()
        if now < as_utc(job.scheduled_at):
            async with transaction():
                await self.jobs.change(
                    job_id,
                    JobChange(
                        status="pending", text=text, lease_expires_at=None
                    ),
                    expected="preparing",
                )
            return
        settings = await self.settings.snapshot()
        file_id = None
        source_bot_id = None
        if job.track_id is not None:
            track = await self.tracks.get(job.track_id)
            if not track.active:
                async with transaction():
                    await self.jobs.change(
                        job_id,
                        JobChange(status="blocked", text=None),
                        expected="preparing",
                    )
                return
            file_id = track.file_id
            source_bot_id = track.bot_id
        if (job.automatic and settings.access.paused) or (
            job.deadline_at and now >= as_utc(job.deadline_at)
        ):
            async with transaction():
                await self.jobs.change(
                    job_id,
                    JobChange(
                        status="pending", text=text, lease_expires_at=None
                    ),
                    expected="preparing",
                )
            return
        async with transaction():
            acquired = await self.gates.acquire(job.channel_id, job.id, now)
            if acquired:
                await self.jobs.change(
                    job_id, JobChange(text=text), expected="preparing"
                )
                sending = await self.jobs.claim_sending(
                    job_id,
                    now,
                    settings.access_revision,
                    job.track_id,
                    file_id,
                )
                if not sending:
                    await self.gates.release(job.channel_id, job.id)
            else:
                sending = False
            if not sending:
                await self.jobs.change(
                    job_id,
                    JobChange(
                        status="pending",
                        text=text,
                        next_attempt_at=now + timedelta(seconds=2),
                        lease_expires_at=None,
                    ),
                    expected="preparing",
                )
        if not sending:
            return
        receipt = await self.telegram.send(
            TelegramSend(
                job_id=job.id,
                chat_id=job.channel_id,
                kind=job.kind,
                text=text,
                file_id=file_id,
                target_message_id=job.target_message_id,
                reply_to=job.target_message_id
                if job.kind == "reply"
                else None,
                source_bot_id=source_bot_id,
                deadline_at=as_utc(job.deadline_at)
                if job.deadline_at
                else None,
            )
        )
        await self._record(job, text, receipt)

    async def _record(
        self, job: PublicationJobModel, text: str, receipt: Receipt
    ) -> None:
        now = self.clock.now()
        async with transaction():
            await self.gates.release(job.channel_id, job.id)
            if receipt.status == "sent" and receipt.message_id is not None:
                await self.jobs.change(
                    job.id,
                    JobChange(
                        status="sent",
                        text=text,
                        message_id=receipt.message_id,
                        sent_at=now,
                        lease_expires_at=None,
                        failure_reason=None,
                    ),
                    expected="sending",
                )
                settings = await self.settings.snapshot()
                if job.channel_id == settings.access.channel_id:
                    if job.kind == "delete":
                        await self.channel.deactivate(
                            job.target_message_id or 0
                        )
                    else:
                        await self.channel.observe(
                            ChannelPostWrite(
                                channel_id=job.channel_id,
                                message_id=receipt.message_id,
                                posted_at=now,
                                edited_at=now if job.kind == "edit" else None,
                                text=text if job.track_id is None else "",
                                caption=text if job.track_id else "",
                                media_kind="audio" if job.track_id else "text",
                                origin="own",
                            )
                        )
                if (
                    not job.automatic
                    and job.kind != "reply"
                    and job.channel_id != job.owner_id
                ):
                    await self.jobs.notify(
                        job,
                        (
                            "حذف شد"
                            if job.kind == "delete"
                            else "ویرایش شد"
                            if job.kind == "edit"
                            else "فرستادم"
                        )
                        + " 🎀\nپیام: "
                        + str(receipt.message_id),
                        now,
                    )
            elif receipt.status == "rate_limited":
                next_at = now + timedelta(
                    seconds=max(1, receipt.retry_after or 1)
                )
                retry = job.attempts < 3 and (
                    job.deadline_at is None
                    or next_at < as_utc(job.deadline_at)
                )
                await self.jobs.change(
                    job.id,
                    JobChange(
                        status="pending" if retry else "failed",
                        next_attempt_at=next_at,
                        failure_reason="telegram_rate_limit",
                        lease_expires_at=None,
                    ),
                    expected="sending",
                )
            else:
                status = (
                    "failed"
                    if receipt.status == "failed"
                    else "delivery_unknown"
                )
                await self.jobs.change(
                    job.id,
                    JobChange(
                        status=status,
                        failure_reason=receipt.reason or "delivery_unknown",
                        lease_expires_at=None,
                    ),
                    expected="sending",
                )
                if job.kind != "reply":
                    await self.jobs.notify(
                        job,
                        "ارسال قطعی نشده؛ دوباره خودکار نمی‌فرستم.\nکار: "
                        + str(job.id)
                        + " · "
                        + status,
                        now,
                    )

    async def recover(self) -> list[int]:
        settings = await self.settings.snapshot()
        now = self.clock.now()
        async with transaction():
            await self.jobs.recover(now)
            missing = await self.reader.unnotified_failures()
            await self.jobs.notify_many(
                [
                    PublicationJobModel(
                        parent_job_id=item.job.id,
                        kind="reply",
                        channel_id=item.job.owner_id,
                        owner_id=item.job.owner_id,
                        automatic=False,
                        text="ارسال قطعی نشده؛ دوباره خودکار نمی‌فرستم.\nکار: "
                        + str(item.job.id)
                        + " · "
                        + item.job.status,
                        scheduled_at=now,
                        next_attempt_at=now,
                    )
                    for item in missing
                ]
            )
        ids = await self.jobs.due_ids(now, settings.window.prepare_seconds)
        return ids

    async def purge(self) -> None:
        settings = await self.settings.snapshot()
        async with transaction():
            await self.jobs.purge_private_text(
                self.clock.now() - timedelta(days=settings.model.history_days)
            )

    async def resolve(
        self, job_id: int, actor_id: int, message_id: int | None
    ) -> None:
        settings = await self.settings.snapshot()
        if actor_id != settings.access.owner_id:
            raise ValueError("Owner required")
        row = await self.jobs.get(job_id)
        if row is None or row.status != "delivery_unknown":
            raise ValueError("Unknown delivery required")
        async with transaction():
            await self.jobs.change(
                job_id,
                JobChange(
                    status="sent" if message_id else "skipped",
                    message_id=message_id,
                    sent_at=self.clock.now() if message_id else None,
                    failure_reason="owner_assertion",
                ),
                expected="delivery_unknown",
            )

    async def retry(
        self, job_id: int, actor_id: int, confirmed: bool = False
    ) -> str:
        settings = await self.settings.snapshot()
        row = await self.jobs.get(job_id)
        if (
            actor_id != settings.access.owner_id
            or row is None
            or row.status not in {"delivery_unknown", "failed"}
        ):
            raise ValueError("Retry not allowed")
        if row.deadline_at and self.clock.now() >= as_utc(row.deadline_at):
            raise ValueError("Publication window ended")
        if not confirmed:
            async with transaction():
                await self.jobs.change(
                    row.id,
                    JobChange(
                        retry_confirmation_expires_at=self.clock.now()
                        + timedelta(minutes=10)
                    ),
                    expected=row.status,
                )
            return (
                "احتمال ارسال تکراری هست. برای تأیید: /retry "
                + str(job_id)
                + " confirm"
            )
        if (
            row.retry_confirmation_expires_at is None
            or self.clock.now() >= as_utc(row.retry_confirmation_expires_at)
        ):
            raise ValueError("Retry confirmation expired")
        async with transaction():
            await self.jobs.change(
                row.id,
                JobChange(
                    status="pending",
                    next_attempt_at=self.clock.now(),
                    failure_reason="owner_retry",
                    retry_confirmation_expires_at=None,
                ),
                expected=row.status,
            )
        return "در صف ارسال قرار گرفت؛ نتیجه را بعد از پاسخ تلگرام می‌گم."
