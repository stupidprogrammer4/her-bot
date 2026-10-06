from datetime import timedelta

from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.transaction import transaction

from her_api.modules.ops.inbox.domain.dtos import InboxChange
from her_api.modules.ops.inbox.domain.models import InboxModel
from her_api.modules.ops.inbox.infra.mysql import InboxRepository
from her_api.modules.ops.inbox.interfaces import IMessageHandler
from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.persona.privacy.app.guard import IdentityGuard
from her_api.shared.clock import Clock
from her_contracts.telegram import Admission, IncomingMessage


class InboxCommands:
    def __init__(
        self,
        repo: InboxRepository,
        settings: ISettingsQueries,
        guard: IdentityGuard,
        handler: IMessageHandler,
        clock: Clock,
    ):
        self.clock = clock
        self.repo, self.settings, self.guard, self.handler = (
            repo,
            settings,
            guard,
            handler,
        )

    async def admit(self, data: IncomingMessage) -> Admission:
        settings = await self.settings.snapshot()
        a = settings.access
        channel = (
            data.channel_post
            and data.chat_type == "channel"
            and data.chat_id == a.channel_id
        )
        private = (
            data.chat_type == "private"
            and data.chat_id == a.owner_id
            and data.sender_id == a.owner_id
        )
        group = (
            data.chat_type in {"group", "supergroup"}
            and data.chat_id == a.group_id
        )
        human = (
            not data.sender_is_bot
            and data.sender_chat_id is None
            and data.sender_id is not None
        )
        if not channel and not (
            human
            and (
                private
                or (
                    group and (data.sender_id == a.owner_id or a.group_enabled)
                )
            )
        ):
            return Admission(accepted=False)
        if group and not data.addressed and not data.text.startswith("/"):
            return Admission(accepted=False)
        clean = data.model_copy(update={"text": self.guard.scrub(data.text)})
        if data.forwarded_post:
            clean.forwarded_post = data.forwarded_post.model_copy(
                update={
                    "text": self.guard.scrub(data.forwarded_post.text),
                    "caption": self.guard.scrub(data.forwarded_post.caption),
                }
            )
        if data.audio:
            clean.audio = data.audio.model_copy(
                update={
                    "title": self.guard.scrub(data.audio.title),
                    "performer": self.guard.scrub(data.audio.performer),
                    "filename": self.guard.scrub(data.audio.filename),
                    "tags": [self.guard.scrub(t) for t in data.audio.tags],
                }
            )
        async with transaction():
            existing = await self.repo.by_update(data.update_id)
            await self.repo.admit(
                InboxModel(
                    update_id=data.update_id, payload=clean.model_dump_json()
                )
            )
        return Admission(accepted=True, replay=existing is not None)

    async def process(self, update_id: int) -> None:
        async with transaction():
            claimed = await self.repo.claim(update_id, self.clock.now())
        if not claimed:
            return
        row = await self.repo.by_update(update_id)
        if row is None:
            raise ValueError("Update not found")
        message = IncomingMessage.model_validate_json(row.payload)
        try:
            await self.handler.handle(message)
        except (ValueError, NotFoundException):
            async with transaction():
                await self.repo.finish(
                    update_id,
                    InboxChange(
                        status="failed", error_code="invalid_operation"
                    ),
                )
            return
        async with transaction():
            await self.repo.finish(update_id, InboxChange(status="completed"))

    async def recover(self) -> list[int]:
        async with transaction():
            ids = await self.repo.recover(self.clock.now())
        return ids

    async def purge(self) -> None:
        settings = await self.settings.snapshot()
        async with transaction():
            await self.repo.purge(
                self.clock.now() - timedelta(days=settings.model.history_days)
            )
