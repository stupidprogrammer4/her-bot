from typing import Any, Literal

from pydantic import BaseModel, Field

GenerationMode = Literal[
    "chat", "channel_caption", "channel_post", "owner_command", "greeting"
]


class ToolFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolFunction


class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class GenerationRequest(BaseModel):
    mode: GenerationMode
    messages: list[ModelMessage] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    private_owner: bool = False
    authenticated_owner: bool = False
    technical: bool = False
    deadline_seconds: float = Field(default=25, gt=0, le=60)


class ModelReply(BaseModel):
    message: ModelMessage
    input_tokens: int = 0
    output_tokens: int = 0
