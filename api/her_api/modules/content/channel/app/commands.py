import json
import secrets
from datetime import timedelta

from anyio import to_thread
from papilio.infra.db.transaction import transaction

from her_api.modules.content.channel.app.export import TelegramExportParser
from her_api.modules.content.channel.domain.models import (
    ChannelImportModel,
    ChannelPostModel,
)
from her_api.modules.content.channel.infra.mysql import (
    ChannelCoverageRepository,
    ChannelImportRepository,
    ChannelPostRepository,
    ImportSessionRepository,
)
from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.persona.privacy.app.guard import IdentityGuard
from her_api.modules.publishing.deliveries.domain.models import (
    PublicationJobModel,
)
from her_api.modules.publishing.deliveries.infra.mysql import (
    PublicationRepository,
)
from her_api.shared.clock import Clock
from her_api.shared.dates import as_utc
from her_contracts.channel import ChannelPostWrite, ImportPreview


class ChannelCommands:
    def __init__(
        self,
        posts: ChannelPostRepository,
        imports: ChannelImportRepository,
        settings: ISettingsQueries,
        guard: IdentityGuard,
        sessions: ImportSessionRepository,
        coverage: ChannelCoverageRepository,
        clock: Clock,
        replies: PublicationRepository,
    ):
        self.clock = clock
        self.replies = replies
        self.posts, self.imports, self.settings, self.guard = (
            posts,
            imports,
            settings,
            guard,
        )
        self.parser = TelegramExportParser()
        self.sessions, self.coverage = sessions, coverage

    async def start_import(self, actor_id: int) -> None:
        settings = await self.settings.snapshot()
        if actor_id != settings.access.owner_id:
            raise ValueError("Owner required")
        async with transaction():
            await self.sessions.open(
                actor_id, self.clock.now() + timedelta(minutes=10)
            )

    async def import_open(self, actor_id: int) -> bool:
        settings = await self.settings.snapshot()
        session = await self.sessions.get(actor_id)
        return (
            actor_id == settings.access.owner_id
            and session is not None
            and self.clock.now() < as_utc(session.expires_at)
        )

    async def heartbeat(self) -> None:
        settings = await self.settings.snapshot()
        now = self.clock.now()
        row = await self.coverage.get(settings.access.channel_id)
        gaps = json.loads(row.gaps_json) if row else []
        if (
            row
            and row.last_heartbeat_at
            and now - as_utc(row.last_heartbeat_at) > timedelta(hours=24)
        ):
            gaps.append(
                {
                    "from": as_utc(row.last_heartbeat_at).isoformat(),
                    "to": now.isoformat(),
                    "reason": "polling_retention_gap_possible",
                }
            )
        async with transaction():
            await self.coverage.heartbeat(
                settings.access.channel_id, now, json.dumps(gaps[-100:])
            )

    async def observe(self, post: ChannelPostWrite) -> None:
        settings = await self.settings.snapshot()
        if post.channel_id != settings.access.channel_id:
            raise ValueError("Channel not allowed")
        data = ChannelPostModel(
            **post.model_dump(exclude={"text", "caption"}),
            text=self.guard.scrub(post.text),
            caption=self.guard.scrub(post.caption),
            active=True,
        )
        async with transaction():
            await self.posts.write(data)
            if post.origin == "live":
                await self.coverage.observe(post.channel_id, self.clock.now())

    async def import_preview(
        self,
        raw: str,
        actor_id: int,
        update_id: int | None = None,
        message_id: int | None = None,
    ) -> ImportPreview:
        async with transaction():
            settings = await self.settings.snapshot()
            if actor_id != settings.access.owner_id:
                raise ValueError("Owner required")
            if update_id is not None:
                existing = await self.imports.by_update(update_id)
                if existing:
                    if existing.owner_id != actor_id:
                        raise ValueError("Import owner mismatch")
                    return ImportPreview.model_validate_json(
                        existing.preview_json
                    )
            if not await self.import_open(actor_id):
                raise ValueError("Open import mode first")
        clean, invalid, matching, title, payload = await to_thread.run_sync(
            self._parse_clean, raw, settings.access.channel_id
        )
        token = secrets.token_urlsafe(18)
        stamps = [r.posted_at for r in clean]
        preview = ImportPreview(
            token=token,
            count=len(clean),
            invalid=invalid,
            matching_channel=matching,
            title=self.guard.scrub(title),
            earliest=min(stamps) if stamps else None,
            latest=max(stamps) if stamps else None,
        )
        async with transaction():
            data = ChannelImportModel(
                token=token,
                owner_id=actor_id,
                update_id=update_id,
                preview_json=preview.model_dump_json(),
                channel_id=settings.access.channel_id,
                payload=payload,
                matching_channel=matching,
                expires_at=self.clock.now() + timedelta(minutes=10),
            )
            if update_id is None:
                await self.imports.create(data)
            else:
                reserved = await self.imports.reserve_update(data)
                preview = ImportPreview.model_validate_json(
                    reserved.preview_json
                )
                await self.replies.reply(
                    PublicationJobModel(
                        kind="reply",
                        owner_id=actor_id,
                        channel_id=actor_id,
                        automatic=False,
                        update_id=update_id,
                        write_slot=2,
                        target_message_id=message_id,
                        text="پیش‌نمایش ورود تاریخچه 🕯️\nمعتبر: "
                        + str(preview.count)
                        + "\nنامعتبر: "
                        + str(preview.invalid)
                        + "\nذخیره: /import_confirm "
                        + preview.token
                        + ("" if preview.matching_channel else " map")
                        + (
                            ""
                            if preview.matching_channel
                            else "\nاین خروجی متعلق به شناسهٔ کانال "
                            "دیگری است؛ "
                            "map فقط با تأیید صریح تو."
                        ),
                        scheduled_at=self.clock.now(),
                        next_attempt_at=self.clock.now(),
                    )
                )
        return preview

    async def import_confirm(
        self, token: str, actor_id: int, explicit_mapping: bool = False
    ) -> int:
        settings = await self.settings.snapshot()
        candidate = await self.imports.by_token(token)
        if (
            candidate is None
            or candidate.owner_id != actor_id
            or actor_id != settings.access.owner_id
            or candidate.channel_id != settings.access.channel_id
        ):
            raise ValueError("Import not allowed")
        if candidate.status == "imported":
            return 0
        posts = await to_thread.run_sync(self._stored_posts, candidate.payload)
        async with transaction():
            row = await self.imports.by_token(token)
            if (
                row is None
                or row.owner_id != actor_id
                or actor_id != settings.access.owner_id
                or row.channel_id != settings.access.channel_id
            ):
                raise ValueError("Import not allowed")
            if row.status == "imported":
                return 0
            if self.clock.now() >= as_utc(row.expires_at) or (
                not row.matching_channel and not explicit_mapping
            ):
                raise ValueError(
                    "Import expired or explicit channel mapping required"
                )
            if not await self.imports.claim(row.id):
                return 0
            await self.posts.write_many(posts)
            await self.imports.consumed(row.id)
        return len(posts)

    def _stored_posts(self, payload: str) -> list[ChannelPostModel]:
        return [
            ChannelPostModel(
                **ChannelPostWrite.model_validate(post).model_dump(),
                active=True,
            )
            for post in json.loads(payload)
        ]

    def _parse_clean(
        self, raw: str, channel_id: int
    ) -> tuple[list[ChannelPostWrite], int, bool, str, str]:
        rows, invalid, matching, title = self.parser.parse(raw, channel_id)
        clean = [
            r.model_copy(
                update={
                    "text": self.guard.scrub(r.text),
                    "caption": self.guard.scrub(r.caption),
                }
            )
            for r in rows
        ]
        payload = json.dumps(
            [r.model_dump(mode="json") for r in clean], ensure_ascii=False
        )
        return clean, invalid, matching, self.guard.scrub(title), payload

    async def deactivate(self, message_id: int) -> None:
        settings = await self.settings.snapshot()
        async with transaction():
            await self.posts.deactivate(settings.access.channel_id, message_id)

    async def purge(self) -> None:
        settings = await self.settings.snapshot()
        async with transaction():
            await self.posts.purge(
                self.clock.now() - timedelta(days=settings.model.channel_days)
            )
            await self.imports.purge(self.clock.now())
