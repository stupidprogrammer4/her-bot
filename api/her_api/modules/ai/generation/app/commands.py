import asyncio
import json
from contextlib import AsyncExitStack
from random import SystemRandom
from typing import Any
from zoneinfo import ZoneInfo

from papilio.infra.db.transaction import transaction

from her_api.modules.ai.generation.app.concurrency import ModelConcurrency
from her_api.modules.ai.generation.domain.dtos import ModelCallChange
from her_api.modules.ai.generation.domain.errors import ModelUnavailable
from her_api.modules.ai.generation.domain.models import ModelCallModel
from her_api.modules.ai.generation.infra.mysql import (
    DailyCallRepository,
    ModelCallRepository,
)
from her_api.modules.ai.generation.interfaces import IModelClient
from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.persona.privacy.app.guard import (
    ANONYMITY_RULE,
    IdentityGuard,
)
from her_api.shared.clock import Clock
from her_contracts.generation import (
    GenerationRequest,
    ModelMessage,
    ModelReply,
)
from her_contracts.policy import SettingsSnapshot


class GenerationCommands:
    def __init__(
        self,
        calls: ModelCallRepository,
        budget: DailyCallRepository,
        model: IModelClient,
        settings: ISettingsQueries,
        concurrency: ModelConcurrency,
        guard: IdentityGuard,
        clock: Clock,
        rng: SystemRandom,
    ):
        self.clock = clock
        self.rng = rng
        (
            self.calls,
            self.budget,
            self.model,
            self.settings,
            self.concurrency,
            self.guard,
        ) = calls, budget, model, settings, concurrency, guard

    async def complete(self, data: GenerationRequest) -> ModelReply:
        settings = await self.settings.snapshot()
        context = {
            "mode": data.mode,
            "public_alias": settings.persona.display_name,
            "owner": data.private_owner,
            "owner_address": settings.persona.owner_address
            if data.private_owner
            else None,
            "facts": [
                f.model_dump()
                for f in settings.persona.facts
                if f.visibility == "public_persona"
                or (data.mode == "chat" and data.private_owner)
            ],
            "data": data.data,
        }
        system = ANONYMITY_RULE + "\n" + settings.persona.system_prompt
        self.guard.require_safe(system)
        messages = [
            ModelMessage(role="system", content=system),
            ModelMessage(
                role="user",
                content=self.guard.scrub(
                    json.dumps(
                        {"trusted_context": context}, ensure_ascii=False
                    )
                ),
            ),
            *[
                m.model_copy(
                    update={
                        "content": self.guard.scrub(m.content)
                        if m.content
                        else None
                    }
                )
                for m in data.messages
            ],
        ]
        tools = (
            data.tools
            if data.mode == "owner_command" and data.authenticated_owner
            else []
        )
        tokens = (
            settings.model.caption_tokens
            if data.mode in {"channel_caption", "channel_post", "greeting"}
            else settings.model.technical_tokens
            if data.technical
            else settings.model.chat_tokens
        )
        try:
            async with (
                asyncio.timeout(data.deadline_seconds),
                AsyncExitStack() as stack,
            ):
                if data.mode in {"chat", "owner_command"}:
                    await stack.enter_async_context(
                        self.concurrency.chat_slots
                    )
                await stack.enter_async_context(self.concurrency.slots)
                try:
                    reply = await self._attempt(
                        settings, data.mode, messages, tools, tokens
                    )
                except ModelUnavailable as error:
                    if not error.retryable:
                        raise
                    await asyncio.sleep(self.rng.uniform(0.1, 0.3))
                    reply = await self._attempt(
                        settings, data.mode, messages, tools, tokens
                    )
        except TimeoutError:
            raise ModelUnavailable("model_timeout") from None
        if reply.message.content:
            self.guard.require_safe(reply.message.content)
        if reply.message.tool_calls and data.mode != "owner_command":
            raise ModelUnavailable("unexpected_tools")
        return reply

    async def _attempt(
        self,
        settings: SettingsSnapshot,
        purpose: str,
        messages: list[ModelMessage],
        tools: list[dict[str, Any]],
        tokens: int,
    ) -> ModelReply:
        day = (
            self.clock.now()
            .astimezone(ZoneInfo(settings.window.timezone))
            .date()
        )
        call_id = None
        async with transaction():
            reserved = await self.budget.reserve(
                day, settings.model.max_daily_calls
            )
            if reserved:
                call = await self.calls.create(
                    ModelCallModel(purpose=purpose, model=settings.model.model)
                )
                call_id = call.id
        if call_id is None:
            raise ModelUnavailable("daily_model_limit")
        try:
            reply = await self.model.complete(
                messages, tools, settings.model, tokens
            )
        except asyncio.CancelledError:
            async with transaction():
                await self.calls.finish(
                    call_id,
                    ModelCallChange(
                        status="failed", error_code="model_cancelled"
                    ),
                )
            raise
        except ModelUnavailable as error:
            async with transaction():
                await self.calls.finish(
                    call_id,
                    ModelCallChange(status="failed", error_code=error.code),
                )
            raise
        async with transaction():
            await self.calls.finish(
                call_id,
                ModelCallChange(
                    status="completed",
                    input_tokens=reply.input_tokens,
                    output_tokens=reply.output_tokens,
                ),
            )
        return reply
