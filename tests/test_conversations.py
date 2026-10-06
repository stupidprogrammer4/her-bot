import asyncio
import json
from datetime import UTC, datetime

import pytest

from her_api.modules.ops.settings.interfaces import ISettingsService
from her_contracts.policy import (
    AccessPolicy,
    ModelPolicy,
    PersonaFact,
    PersonaPolicy,
)
from tests.conftest import CHANNEL, GROUP, OWNER
from tests.messages import message

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_member_anonymous_bot_and_channel_post_cannot_run_owner_actions(
    native,
):
    attempts = [
        message(201, "/resume").model_copy(
            update={
                "chat_id": GROUP,
                "chat_type": "supergroup",
                "sender_id": 22222,
            }
        ),
        message(202, "شمع زیبا به بچه‌ها سلام کن").model_copy(
            update={
                "chat_id": GROUP,
                "chat_type": "supergroup",
                "sender_chat_id": GROUP,
            }
        ),
        message(203, "/publish forged").model_copy(
            update={"sender_is_bot": True}
        ),
        message(204, "/resume").model_copy(
            update={
                "chat_id": CHANNEL,
                "chat_type": "channel",
                "channel_post": True,
            }
        ),
    ]
    results = await asyncio.gather(*(native.post(data) for data in attempts))
    assert [r["accepted"] for r in results] == [False, False, False, True]
    assert not await native.rows("SELECT id FROM tbl_owner_actions")
    assert not native.services.model_requests
    access = (
        await native.rows(
            "SELECT value FROM tbl_settings WHERE `key`='access'"
        )
    )[0]
    assert json.loads(access["value"])["paused"] is True
    posts = await native.rows(
        "SELECT text FROM tbl_channel_posts WHERE message_id=205"
    )
    assert posts == [{"text": "/resume"}]


async def test_group_prompt_excludes_private_facts_and_history(
    native,
):
    async with native.scope() as scope:
        service = await scope.get(ISettingsService)
        access = await service.get("access")
        assert isinstance(access.value, AccessPolicy)
        await service.write(
            "access",
            access.value.model_copy(update={"group_enabled": True}),
            access.revision,
        )
        profile = await service.get("persona")
        assert isinstance(profile.value, PersonaPolicy)
        updated = profile.value.model_copy(
            update={
                "facts": profile.value.facts
                + [
                    PersonaFact(
                        key="private-test",
                        content="PRIVATE_OWNER_DETAIL",
                        visibility="owner_private",
                    )
                ]
            }
        )
        await service.write("persona", updated, profile.revision)
    native.services.model_replies = [
        {"role": "assistant", "content": "این جواب مخصوص گفت‌وگوی خودمونه 🎀"}
    ]
    await native.post(message(211, "PRIVATE_CONVERSATION_DETAIL"))
    await native.services.received(
        lambda r: "این جواب مخصوص" in r.get("text", "")
    )
    first = json.dumps(native.services.model_requests[-1], ensure_ascii=False)
    assert (
        "PRIVATE_OWNER_DETAIL" in first
        and "PRIVATE_CONVERSATION_DETAIL" in first
    )
    native.services.model_replies = [
        {
            "role": "assistant",
            "content": "سلام عضو گروه؛ این جواب برای گفت‌وگوی عمومیه",
        }
    ]
    await native.post(
        message(212, "Her سلام").model_copy(
            update={
                "sender_id": 22222,
                "chat_id": GROUP,
                "chat_type": "supergroup",
            }
        )
    )
    await native.services.received(
        lambda r: "سلام عضو گروه" in r.get("text", "")
    )
    public = json.dumps(native.services.model_requests[-1], ensure_ascii=False)
    assert (
        "PRIVATE_OWNER_DETAIL" not in public
        and "PRIVATE_CONVERSATION_DETAIL" not in public
    )
    assert "tools" not in native.services.model_requests[-1]
    assert native.services.model_requests[-1]["provider"] == {
        "data_collection": "deny",
        "zdr": True,
        "require_parameters": True,
    }
    history = await native.rows(
        (
            "SELECT chat_id,user_id,user_text FROM "
            "tbl_conversation_pairs ORDER BY id"
        )
    )
    assert (
        history[0]["chat_id"] == OWNER
        and history[1]["chat_id"] == GROUP
        and history[1]["user_id"] == 22222
    )
    await native.post(
        message(213, "/forget").model_copy(
            update={
                "sender_id": 22222,
                "chat_id": GROUP,
                "chat_type": "supergroup",
            }
        )
    )
    remaining = await native.rows(
        "SELECT chat_id,user_id FROM tbl_conversation_pairs"
    )
    assert remaining == [{"chat_id": OWNER, "user_id": OWNER}]


async def test_owner_tool_rounds_are_persisted_complete_and_publish_once(
    native,
):
    native.services.model_replies = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "publish_text",
                        "arguments": json.dumps(
                            {
                                "text": "پست عمومی آزمون",
                                "destination": "channel",
                            }
                        ),
                    },
                }
            ],
        },
        {"role": "assistant", "content": "ارسال شد، همه‌چی کامله!"},
    ]
    await native.post(message(221, "شمع زیبا این متن رو منتشر کن"))
    await native.services.received(
        lambda r: (
            r.get("text") == "پست عمومی آزمون"
            and int(r.get("chat_id", 0)) == CHANNEL
        )
    )
    await native.services.received(
        lambda r: (
            "فرستادم" in r.get("text", "")
            and int(r.get("chat_id", 0)) == OWNER
        )
    )
    rows = await native.rows(
        (
            "SELECT status FROM tbl_publication_jobs WHERE "
            "update_id=221 AND write_slot=1"
        )
    )
    assert rows == [{"status": "sent"}]
    assert (
        len(
            await native.rows(
                "SELECT id FROM tbl_owner_actions WHERE update_id=221"
            )
        )
        == 1
    )
    await native.services.received(
        lambda r: (
            "در صف ارسال قرار گرفت" in r.get("text", "")
            and int(r.get("chat_id", 0)) == OWNER
        )
    )
    final = native.services.model_requests[-1]["messages"]
    assert any(
        m.get("tool_call_id") == "call-1" and m["role"] == "tool"
        for m in final
    )
    assert any(
        m.get("tool_calls") and m["tool_calls"][0]["id"] == "call-1"
        for m in final
    )
    assert not any(
        r.get("text") == "ارسال شد، همه‌چی کامله!"
        for r in native.services.telegram_requests
    )
    await native.post(message(221, "شمع زیبا این متن رو منتشر کن"))
    assert (
        len(
            await native.rows(
                (
                    "SELECT id FROM tbl_publication_jobs WHERE "
                    "update_id=221 AND write_slot=1"
                )
            )
        )
        == 1
    )


async def test_owner_write_tools_do_not_receive_old_private_history(native):
    native.services.model_replies = [
        {"role": "assistant", "content": "این حرف خصوصی پیش خودمون می‌مونه"}
    ]
    await native.post(message(231, "PRIVATE_PAST_CONVERSATION"))
    await native.services.received(
        lambda r: "این حرف خصوصی" in r.get("text", "")
    )
    await native.execute(
        "UPDATE tbl_chat_requests SET created_at=:time WHERE update_id=231",
        {"time": datetime(2026, 10, 1, tzinfo=UTC)},
    )
    native.services.model_replies = [
        {"role": "assistant", "content": "پیشنهاد عمومی آماده‌ست؛ ارسال نشده"}
    ]
    await native.post(message(232, "شمع زیبا یک متن منتشر کن"))
    await native.services.received(
        lambda r: "هنوز هیچ کاری انجام نشده" in r.get("text", "")
    )
    assert "PRIVATE_PAST_CONVERSATION" not in json.dumps(
        native.services.model_requests[-1], ensure_ascii=False
    )
    assert not await native.rows(
        (
            "SELECT id FROM tbl_publication_jobs WHERE "
            "update_id=232 AND write_slot=1"
        )
    )


async def test_model_hard_daily_limit_prevents_request_and_uses_chat_fallback(
    native,
):
    async with native.scope() as scope:
        service = await scope.get(ISettingsService)
        current = await service.get("model")
        assert isinstance(current.value, ModelPolicy)
        await service.write(
            "model",
            current.value.model_copy(update={"max_daily_calls": 1}),
            current.revision,
        )
    await native.execute(
        "INSERT INTO tbl_daily_calls(day,calls) VALUES(:day,1)",
        {
            "day": datetime.now(UTC)
            .astimezone(__import__("zoneinfo").ZoneInfo("Asia/Tehran"))
            .date()
        },
    )
    await native.post(message(241, "سلام"))
    await native.services.received(
        lambda r: "الان جوابم گیر کرده" in r.get("text", "")
    )
    assert not native.services.model_requests
    assert not await native.rows("SELECT id FROM tbl_conversation_pairs")
