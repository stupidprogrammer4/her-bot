"""Live model checks for the specific reproduced response defects."""

import json
import os
from pathlib import Path

import httpx
import pytest
from dotenv import dotenv_values
from pydantic import SecretStr

from her_api.config.settings import HerSettings, ModelCredentials
from her_api.modules.ai.generation.app.prompts import mode_instructions
from her_api.modules.ai.generation.infra.groq import GroqClient
from her_api.modules.persona.privacy.app.defaults import initial_persona
from her_api.modules.persona.privacy.app.guard import ANONYMITY_RULE
from her_contracts.generation import ModelMessage
from her_contracts.policy import ModelPolicy


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("GROQ_LIVE") != "1", reason="Opt-in live Groq")
@pytest.mark.parametrize(
    "mode,text,data,forbidden",
    [
        (
            "chat",
            "امروز خیلی خسته‌ام و حوصله نصیحت و سؤال ندارم.",
            {},
            ["استراحت", "نفس", "بخواب", "نوشیدنی", "؟", "?"],
        ),
        (
            "channel_caption",
            "برای این آهنگ کپشن بنویس.",
            {
                "mood": "neutral",
                "publication_local_time": "2026-10-13T15:00:00+03:30",
            },
            ["ملایم", "آرام", "امشب", "پیانو", "غمگین", "؟", "?"],
        ),
        (
            "channel_post",
            "یک پست کوتاه درباره گربه‌ها بنویس.",
            {
                "topic": "cats",
                "publication_local_time": "2026-10-13T14:00:00+03:30",
            },
            ["امشب", "شب‌", "می‌خوای", "؟", "?"],
        ),
    ],
)
async def test_live_mode_obeys_explicit_style_constraints(
    mode, text, data, forbidden
):
    key = dotenv_values(Path(__file__).parents[1] / ".env")["GROQ_API_KEY"]
    assert key
    settings = HerSettings.model_construct(
        ai=ModelCredentials(api_key=SecretStr(key))
    )
    persona = initial_persona()
    # Keep the old example to exercise existing stored personas.
    system = "\n".join(
        (
            ANONYMITY_RULE,
            persona.system_prompt,
            "For tiredness: یه کم استراحت کن؛ اگه خواستی حرف بزنیم، اینجام.",
            mode_instructions(mode),
        )
    )
    context = {
        "mode": mode,
        "public_alias": persona.display_name,
        "owner": False,
        "owner_address": None,
        "facts": [],
        "data": data,
    }
    messages = [
        ModelMessage(role="system", content=system),
        ModelMessage(
            role="user", content=json.dumps({"trusted_context": context})
        ),
        ModelMessage(role="user", content=text),
    ]
    async with httpx.AsyncClient(timeout=45) as http:
        result = await GroqClient(http, settings).complete(
            messages, [], ModelPolicy(), 320
        )
    response = result.message.content
    assert response
    assert len(response.split()) <= 80
    assert not any(word in response for word in forbidden), response
