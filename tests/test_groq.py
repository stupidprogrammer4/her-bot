import json

import httpx
import pytest
from pydantic import SecretStr

from her_api.config.settings import HerSettings, ModelCredentials
from her_api.modules.ai.generation.infra.groq import GroqClient
from her_contracts.generation import ModelMessage
from her_contracts.policy import ModelPolicy


@pytest.mark.asyncio
async def test_groq_completion_uses_native_parameters():
    def respond(request):
        payload = json.loads(request.content)
        assert request.url == "https://api.groq.com/openai/v1/chat/completions"
        assert "provider" not in payload
        assert "reasoning" not in payload
        assert payload["reasoning_effort"] == "low"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "سلام"}}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )

    settings = HerSettings.model_construct(
        ai=ModelCredentials(api_key=SecretStr("test"))
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond)
    ) as http:
        result = await GroqClient(http, settings).complete(
            [ModelMessage(role="user", content="سلام")],
            [],
            ModelPolicy(model="openai/gpt-oss-120b", reasoning_effort="low"),
            320,
        )
    assert result.message.content == "سلام"
    assert result.input_tokens == 5
