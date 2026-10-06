import json
from datetime import timedelta

from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.transaction import transaction

from her_api.modules.ai.generation.domain.errors import ModelUnavailable
from her_api.modules.ai.generation.interfaces import IGenerationCommands
from her_api.modules.conversations.actions.app.capabilities import (
    OwnerCapabilities,
)
from her_api.modules.conversations.actions.domain.tools import READ_TOOLS
from her_api.modules.conversations.actions.interfaces import IOwnerActions
from her_api.modules.conversations.chat.domain.dtos import ChatChange
from her_api.modules.conversations.chat.domain.models import (
    ChatRequestModel,
    ConversationPairModel,
)
from her_api.modules.conversations.chat.infra.mysql import (
    ChatRequestRepository,
    ConversationPairRepository,
    ConversationRepository,
)
from her_api.modules.conversations.chat.infra.readers import ConversationReader
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
from her_contracts.generation import GenerationRequest, ModelMessage
from her_contracts.telegram import IncomingMessage


class ChatCommands:
    def __init__(
        self,
        requests: ChatRequestRepository,
        conversations: ConversationRepository,
        pairs: ConversationPairRepository,
        reader: ConversationReader,
        replies: PublicationRepository,
        generation: IGenerationCommands,
        actions: IOwnerActions,
        settings: ISettingsQueries,
        guard: IdentityGuard,
        clock: Clock,
    ):
        self.clock = clock
        (
            self.requests,
            self.conversations,
            self.pairs,
            self.reader,
            self.replies,
            self.generation,
            self.actions,
            self.settings,
            self.guard,
        ) = (
            requests,
            conversations,
            pairs,
            reader,
            replies,
            generation,
            actions,
            settings,
            guard,
        )
        self.capabilities = OwnerCapabilities()

    async def admit(self, data: IncomingMessage) -> bool:
        settings = await self.settings.snapshot()
        if (
            data.sender_id is None
            or data.sender_is_bot
            or data.sender_chat_id is not None
            or data.channel_post
        ):
            return False
        owner = data.sender_id == settings.access.owner_id
        private = (
            owner
            and data.chat_type == "private"
            and data.chat_id == data.sender_id
        )
        group = (
            data.chat_id == settings.access.group_id
            and data.chat_type in {"group", "supergroup"}
        )
        if not private and not (
            group
            and data.addressed
            and (owner or settings.access.group_enabled)
        ):
            return False
        stats = await self.reader.admission(
            data.sender_id, self.clock.now() - timedelta(hours=1)
        )
        if stats.hourly_count >= settings.model.hourly_chat_limit or (
            stats.latest_at
            and (self.clock.now() - as_utc(stats.latest_at)).total_seconds()
            < settings.model.minimum_chat_seconds
        ):
            return False
        async with transaction():
            await self.requests.admit(
                ChatRequestModel(
                    update_id=data.update_id,
                    chat_id=data.chat_id,
                    user_id=data.sender_id,
                    message_id=data.message_id,
                    private_owner=private,
                    authenticated_owner=owner,
                    text=self.guard.scrub(data.text),
                    next_attempt_at=self.clock.now(),
                )
            )
        return True

    async def step(self, request_id: int) -> bool:
        now = self.clock.now()
        async with transaction():
            claimed = await self.requests.claim(request_id, now)
            if not claimed:
                return False
            record = await self.requests.get(request_id)
            if record is None:
                raise ValueError("Chat request not found")
            row = ChatRequestModel.model_validate(record.model_dump())
            acquired = await self.conversations.acquire(
                row.chat_id, row.user_id, row.id, now
            )
            if not acquired:
                await self.requests.change(
                    row.id,
                    ChatChange(
                        status="pending",
                        next_attempt_at=now + timedelta(seconds=2),
                        lease_expires_at=None,
                    ),
                )
                return False
        settings = await self.settings.snapshot()
        if (
            row.started_at
            and (now - as_utc(row.started_at)).total_seconds() >= 60
        ):
            await self._finish(
                row, settings.persona.chat_fallback, remember=False
            )
            return False
        messages = [
            ModelMessage.model_validate(m) for m in json.loads(row.messages)
        ]
        if row.phase == "initial":
            allowed = (
                self.capabilities.allowed(row.text)
                if row.authenticated_owner
                else frozenset()
            )
            use_tools = (
                row.authenticated_owner
                and self.capabilities.uses_tools(row.text, allowed)
            )
            pairs = (
                []
                if use_tools
                else await self.pairs.history(
                    row.chat_id,
                    row.user_id,
                    now - timedelta(days=settings.model.history_days),
                    settings.model.history_messages // 2,
                )
            )
            history, used = [], len(row.text)
            for pair in pairs:
                length = len(pair.user_text) + len(pair.assistant_text)
                if used + length > settings.model.history_chars:
                    break
                used += length
                history.append(pair)
            messages = [
                m
                for p in reversed(history)
                for m in (
                    ModelMessage(role="user", content=p.user_text),
                    ModelMessage(role="assistant", content=p.assistant_text),
                )
            ]
            messages.append(
                ModelMessage(
                    role="user",
                    content=row.text[: settings.model.history_chars],
                )
            )
            allowed = (
                self.capabilities.allowed(row.text)
                if row.authenticated_owner
                else frozenset()
            )
            async with transaction():
                await self.requests.change(
                    row.id,
                    ChatChange(
                        messages=json.dumps(
                            [
                                m.model_dump(exclude_none=True)
                                for m in messages
                            ],
                            ensure_ascii=False,
                        ),
                        capabilities=json.dumps(sorted(allowed)),
                        phase="model",
                        started_at=now,
                        status="pending",
                        lease_expires_at=None,
                    ),
                )
            return True
        allowed = frozenset(json.loads(row.capabilities))
        if row.phase == "tools":
            calls = next(
                (
                    m.tool_calls
                    for m in reversed(messages)
                    if m.role == "assistant" and m.tool_calls
                ),
                None,
            )
            if not calls or row.tool_cursor >= len(calls):
                raise ValueError("Missing tool calls")
            call = calls[row.tool_cursor]
            try:
                result = await self.actions.execute(
                    row.update_id,
                    row.user_id,
                    call.function.name,
                    call.function.arguments,
                    allowed,
                )
            except (ValueError, NotFoundException):
                result = (
                    '{"status":"denied","reason":"invalid_or_'
                    'unauthorized_tool"}'
                )
            messages.append(
                ModelMessage(role="tool", tool_call_id=call.id, content=result)
            )
            more = row.tool_cursor + 1 < len(calls)
            async with transaction():
                await self.requests.change(
                    row.id,
                    ChatChange(
                        messages=json.dumps(
                            [
                                m.model_dump(exclude_none=True)
                                for m in messages
                            ],
                            ensure_ascii=False,
                        ),
                        phase="tools" if more else "model",
                        tool_cursor=row.tool_cursor + 1 if more else 0,
                        status="pending",
                        lease_expires_at=None,
                    ),
                )
            return True
        if row.round >= settings.model.max_rounds:
            await self._finish(
                row,
                "این درخواست همین\u200cجا متوقف شد؛ نتیجهٔ ارس"
                "ال را جدا اعلام می\u200cکنم.",
                remember=False,
            )
            return False
        remaining = max(
            0.01, 60 - (now - as_utc(row.started_at or now)).total_seconds()
        )
        tool_mode = row.authenticated_owner and self.capabilities.uses_tools(
            row.text, allowed
        )
        try:
            reply = await self.generation.complete(
                GenerationRequest(
                    mode="owner_command" if tool_mode else "chat",
                    messages=messages,
                    private_owner=row.private_owner,
                    authenticated_owner=row.authenticated_owner,
                    tools=self.capabilities.schemas(allowed)
                    if tool_mode
                    else [],
                    technical=any(
                        term in row.text.casefold()
                        for term in (
                            "کد بنویس",
                            "توضیح فنی",
                            "python",
                            "sql",
                            "javascript",
                        )
                    ),
                    deadline_seconds=min(25, remaining),
                )
            )
        except (ModelUnavailable, ValueError):
            await self._finish(
                row, settings.persona.chat_fallback, remember=False
            )
            return False
        if reply.message.tool_calls:
            calls = reply.message.tool_calls
            writes = [c for c in calls if c.function.name not in READ_TOOLS]
            if len(calls) > 8 or len(writes) > 1:
                await self._finish(
                    row,
                    "درخواست ابزار معتبر نبود؛ کاری انجام ندادم.",
                    remember=False,
                )
                return False
            messages.append(reply.message)
            async with transaction():
                await self.requests.change(
                    row.id,
                    ChatChange(
                        messages=json.dumps(
                            [
                                m.model_dump(exclude_none=True)
                                for m in messages
                            ],
                            ensure_ascii=False,
                        ),
                        round=row.round + 1,
                        phase="tools",
                        tool_cursor=0,
                        status="pending",
                        lease_expires_at=None,
                    ),
                )
            return True
        text = (reply.message.content or "").strip()
        if not text or len(text) > 3500:
            text = settings.persona.chat_fallback
        tool_used = any(m.role == "tool" for m in messages)
        denied = any(
            m.role == "tool" and '"status":"denied"' in (m.content or "")
            for m in messages
        )
        if not tool_used and allowed - READ_TOOLS:
            text = (
                "برای این درخواست هنوز هیچ کاری انجام نشده؛ ارسال "
                "تأییدشده‌ای ندارم."
            )
        if tool_used and any(
            '"delivered": false' in (m.content or "")
            for m in messages
            if m.role == "tool"
        ):
            text = (
                "در صف ارسال قرار گرفت؛ وقتی تلگرام تأیید"
                " کرد خصوصی خبر می\u200cدم 🎀"
            )
        if denied:
            text = (
                "این کار مجاز یا معتبر نبود؛ هیچ ارسال تأییدشده‌ای انجام نشده."
            )
        private_text = None
        if tool_used and not row.private_owner:
            private_text = self.guard.require_safe(text)
            text = "درخواستت بررسی شد؛ جزئیات در صف پیام خصوصی قرار گرفت 🎀"
        await self._finish(
            row,
            self.guard.require_safe(text),
            remember=not tool_used,
            private_text=private_text,
        )
        return False

    async def _finish(
        self,
        row: ChatRequestModel,
        text: str,
        *,
        remember: bool,
        private_text: str | None = None,
    ) -> None:
        now = self.clock.now()
        async with transaction():
            fresh = await self.requests.get(row.id)
            if fresh is None or fresh.status != "running":
                return
            await self.replies.reply(
                PublicationJobModel(
                    kind="reply",
                    owner_id=row.user_id,
                    channel_id=row.chat_id,
                    automatic=False,
                    update_id=row.update_id,
                    write_slot=2,
                    text=text,
                    target_message_id=row.message_id,
                    scheduled_at=now,
                    next_attempt_at=now,
                )
            )
            if private_text and row.authenticated_owner:
                await self.replies.reply(
                    PublicationJobModel(
                        kind="reply",
                        owner_id=row.user_id,
                        channel_id=row.user_id,
                        automatic=False,
                        update_id=row.update_id,
                        write_slot=3,
                        text=private_text,
                        scheduled_at=now,
                        next_attempt_at=now,
                    )
                )
            if remember:
                await self.pairs.save(
                    ConversationPairModel(
                        request_id=row.id,
                        chat_id=row.chat_id,
                        user_id=row.user_id,
                        user_text=row.text,
                        assistant_text=text,
                    )
                )
            await self.requests.change(
                row.id,
                ChatChange(
                    status="completed", messages="[]", lease_expires_at=None
                ),
            )
            await self.conversations.release(row.chat_id, row.user_id, row.id)

    async def recover(self) -> list[int]:
        async with transaction():
            ids = await self.requests.recover(self.clock.now())
        return ids

    async def purge(self) -> None:
        settings = await self.settings.snapshot()
        before = self.clock.now() - timedelta(days=settings.model.history_days)
        async with transaction():
            await self.requests.purge(before)
            await self.pairs.purge(before)

    async def forget(self, chat_id: int, user_id: int) -> None:
        async with transaction():
            await self.requests.forget(chat_id, user_id)
            await self.pairs.forget(chat_id, user_id)
