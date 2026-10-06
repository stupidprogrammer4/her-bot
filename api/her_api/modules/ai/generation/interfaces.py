from collections.abc import Awaitable
from typing import Any, Protocol

from her_contracts.generation import (
    GenerationRequest,
    ModelMessage,
    ModelReply,
)
from her_contracts.policy import ModelPolicy


class IModelClient(Protocol):
    def complete(
        self,
        messages: list[ModelMessage],
        tools: list[dict[str, Any]],
        policy: ModelPolicy,
        tokens: int,
    ) -> Awaitable[ModelReply]: ...


class IGenerationCommands(Protocol):
    def complete(self, data: GenerationRequest) -> Awaitable[ModelReply]: ...
