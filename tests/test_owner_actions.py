import json
from datetime import UTC, datetime, timedelta

import pytest

from her_api.modules.conversations.actions.interfaces import IOwnerActions
from her_api.modules.publishing.deliveries.interfaces import (
    IPublicationCommands,
)
from tests.conftest import CHANNEL, OWNER
from tests.messages import message
from tests.test_publishing import seed_job

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_invalid_track_tool_rolls_back_and_finishes_chat_safely(native):
    native.services.model_replies = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "missing-track",
                    "type": "function",
                    "function": {
                        "name": "publish_track",
                        "arguments": json.dumps({"track_id": 999999}),
                    },
                }
            ],
        },
        {"role": "assistant", "content": "آهنگ رو پخش کردم!"},
    ]
    await native.post(message(601, "شمع زیبا آهنگ 999999 رو پخش کن"))
    await native.services.received(
        lambda r: "این کار مجاز یا معتبر نبود" in r.get("text", "")
    )
    assert not await native.rows(
        "SELECT id FROM tbl_owner_actions WHERE update_id=601"
    )
    assert not await native.rows(
        "SELECT id FROM tbl_publication_jobs "
        "WHERE update_id=601 AND write_slot=1"
    )
    assert not any(
        int(r.get("chat_id", 0)) == CHANNEL
        for r in native.services.telegram_requests
    )
    assert not any(
        r.get("text") == "آهنگ رو پخش کردم!"
        for r in native.services.telegram_requests
    )


async def test_quoted_greeting_is_data_and_does_not_publish(native):
    native.services.model_replies = [
        {
            "role": "assistant",
            "content": "این فقط متن نقل‌شده‌ست؛ چیزی منتشر نشده",
        }
    ]
    await native.post(message(602, "معنی «شمع زیبا به بچه‌ها سلام کن» چیه؟"))
    await native.services.received(
        lambda r: "این فقط متن نقل‌شده" in r.get("text", "")
    )
    assert not await native.rows(
        "SELECT id FROM tbl_owner_actions WHERE update_id=602"
    )
    assert not any(
        int(r.get("chat_id", 0)) == CHANNEL
        for r in native.services.telegram_requests
    )


@pytest.mark.parametrize("through_inbox", [False, True])
async def test_delete_requires_owner_confirmation_and_a_recorded_own_post(
    native,
    through_inbox,
):
    await native.post(message(611, "/publish پست قابل حذف"))
    await native.services.received(
        lambda r: (
            "فرستادم" in r.get("text", "")
            and int(r.get("chat_id", 0)) == OWNER
        )
    )
    post = (
        await native.rows(
            "SELECT message_id FROM tbl_publication_jobs "
            "WHERE update_id=611 AND write_slot=1"
        )
    )[0]["message_id"]
    async with native.scope() as scope:
        actions = await scope.get(IOwnerActions)
        result = json.loads(
            await actions.execute(
                612,
                OWNER,
                "request_delete_own_post",
                json.dumps({"message_id": post}),
                frozenset({"request_delete_own_post"}),
            )
        )
    token = result["command"].split()[1]
    async with native.scope() as scope:
        actions = await scope.get(IOwnerActions)
        with pytest.raises(ValueError):
            await actions.confirm_delete(613, OWNER + 1, token)
    if not through_inbox:
        async with native.scope() as scope:
            actions = await scope.get(IOwnerActions)
            await actions.confirm_delete(614, OWNER, token)
    await native.post(message(614, "/delete_confirm " + token))
    await native.services.received(
        lambda r: (
            "حذف شد" in r.get("text", "") and int(r.get("chat_id", 0)) == OWNER
        )
    )
    assert (
        len(
            [
                r
                for r in native.services.telegram_requests
                if r["method"] == "deleteMessage"
                and int(r["message_id"]) == post
            ]
        )
        == 1
    )
    assert await native.rows(
        "SELECT active FROM tbl_channel_posts WHERE message_id=:id",
        {"id": post},
    ) == [{"active": 0}]
    await native.post(message(614, "/delete_confirm " + token))
    assert (
        len(
            [
                r
                for r in native.services.telegram_requests
                if r["method"] == "deleteMessage"
            ]
        )
        == 1
    )


async def test_unknown_retry_requires_confirmation_and_respects_deadline(
    native,
):
    job = await seed_job(
        native, status="delivery_unknown", text="بازفرستادن تأییدشده"
    )
    await native.post(message(621, "/retry " + str(job)))
    await native.services.received(
        lambda r: "احتمال ارسال تکراری" in r.get("text", "")
    )
    assert not any(
        r.get("text") == "بازفرستادن تأییدشده"
        for r in native.services.telegram_requests
    )
    await native.post(message(622, "/retry " + str(job) + " confirm"))
    await native.services.received(
        lambda r: r.get("text") == "بازفرستادن تأییدشده"
    )
    expired = await seed_job(
        native,
        status="delivery_unknown",
        automatic=True,
        deadline_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    async with native.scope() as scope:
        publications = await scope.get(IPublicationCommands)
        with pytest.raises(ValueError):
            await publications.retry(expired, OWNER, True)
    assert (
        await native.rows(
            "SELECT status FROM tbl_publication_jobs WHERE id=:id",
            {"id": expired},
        )
    )[0]["status"] == "delivery_unknown"
