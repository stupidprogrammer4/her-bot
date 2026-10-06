from typing import Any

import httpx
from pydantic import ValidationError

from her_api.config.settings import HerSettings
from her_api.modules.ai.generation.domain.errors import ModelUnavailable
from her_contracts.generation import ModelMessage, ModelReply
from her_contracts.policy import ModelPolicy


class OpenRouterClient:
    def __init__(self, client: httpx.AsyncClient, settings: HerSettings):
        self.client = client
        self.settings = settings.ai

    async def complete(
        self,
        messages: list[ModelMessage],
        tools: list[dict[str, Any]],
        policy: ModelPolicy,
        tokens: int,
    ) -> ModelReply:
        if not self.settings.api_key.get_secret_value():
            raise ModelUnavailable("model_not_configured")
        payload: dict[str, Any] = {
            "model": policy.model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
            "temperature": policy.temperature,
            "max_tokens": tokens,
            "stream": False,
            "provider": {
                "data_collection": "deny",
                "zdr": True,
                "require_parameters": True,
            },
        }
        if policy.reasoning_effort is not None:
            payload["reasoning"] = {"effort": policy.reasoning_effort}
        if tools:
            payload.update(tools=tools, parallel_tool_calls=False)
        try:
            response = await self.client.post(
                self.settings.endpoint,
                headers={
                    "Authorization": "Bearer "
                    + self.settings.api_key.get_secret_value()
                },
                json=payload,
            )
        except httpx.RequestError:
            raise ModelUnavailable("model_network", retryable=True) from None
        if response.status_code >= 400:
            raise ModelUnavailable(
                f"model_http_{response.status_code}",
                retryable=response.status_code == 429
                or response.status_code >= 500,
            )
        try:
            body = response.json()
            if body.get("error"):
                raise ModelUnavailable("model_error")
            reply = ModelMessage.model_validate(body["choices"][0]["message"])
            if reply.role != "assistant" or (
                not reply.content and not reply.tool_calls
            ):
                raise ModelUnavailable("model_empty")
            usage = body.get("usage") or {}
            return ModelReply(
                message=reply,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            )
        except (ValueError, KeyError, IndexError, TypeError, ValidationError):
            raise ModelUnavailable("model_invalid_response") from None
