import os
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values
from pydantic import SecretStr

from her_api.config.settings import HerSettings, ModelCredentials
from her_api.modules.ai.generation.infra.groq import GroqClient
from her_contracts.generation import ModelMessage
from her_contracts.policy import ModelPolicy


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("GROQ_LIVE") != "1", reason="Opt-in live Groq")
async def test_live_adapter_completes_tool_round_trip():
    key = dotenv_values(Path(__file__).parents[1] / ".env")["GROQ_API_KEY"]
    assert key
    settings = HerSettings.model_construct(
        ai=ModelCredentials(api_key=SecretStr(key))
    )
    policy = ModelPolicy(model="qwen/qwen3.8-27b", reasoning_effort=None)
    messages = [
        ModelMessage(
            role="system",
            content=(
                "Call read_probe before answering. "
                "Use its returned value verbatim."
            ),
        ),
        ModelMessage(role="user", content="Call read_probe now."),
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_probe",
                "description": "Read the probe value",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    async with httpx.AsyncClient(timeout=45) as http:
        model = GroqClient(http, settings)
        reply = await model.complete(messages, tools, policy, 900)
        assert reply.message.tool_calls
        call = reply.message.tool_calls[0]
        assert call.function.name == "read_probe"
        messages.extend(
            [
                reply.message,
                ModelMessage(
                    role="tool",
                    tool_call_id=call.id,
                    content="GROQ_PROBE_731",
                ),
            ]
        )
        final = await model.complete(messages, [], policy, 900)
    assert "GROQ_PROBE_731" in (final.message.content or "")
    assert final.input_tokens > 0
