import json
from datetime import UTC, datetime

import pytest
from aiogram import Dispatcher
from aiogram.types import Update

from her_bot.app.acknowledgements import DurableAcknowledgements
from her_bot.app.heartbeat import PollingHeartbeat
from her_bot.app.updates import UpdateHandler
from her_contracts.channel import ChannelPostWrite
from tests.conftest import BOT_ID, CHANNEL, OWNER
from tests.messages import message

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_callback_back_uses_sdk_queue_and_returns_home(native):
    configuration = await native.backend.configuration()
    acknowledgements = DurableAcknowledgements()
    handler = UpdateHandler(
        native.bot,
        native.backend,
        configuration,
        "test_her_bot",
        acknowledgements,
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(handler.router)
    update = Update.model_validate(
        {
            "update_id": 501,
            "callback_query": {
                "id": "callback-home",
                "chat_instance": "test",
                "data": "start",
                "from": {"id": OWNER, "is_bot": False, "first_name": "Test"},
                "message": {
                    "message_id": 70,
                    "date": int(datetime.now(UTC).timestamp()),
                    "chat": {"id": OWNER, "type": "private"},
                    "from": {
                        "id": BOT_ID,
                        "is_bot": True,
                        "first_name": "Her",
                    },
                    "text": "submenu",
                },
            },
        }
    )
    await dispatcher.feed_update(native.bot, update)
    home = await native.services.received(
        lambda request: "من شمع زیبام" in request.get("text", "")
    )
    assert json.loads(home["reply_parameters"])["message_id"] == 70
    assert acknowledgements.highest_committed == 501
    assert any(
        r["method"] == "answerCallbackQuery"
        for r in native.services.telegram_requests
    )
    assert (
        len(
            await native.rows(
                "SELECT id FROM tbl_publication_jobs WHERE update_id=501"
            )
        )
        == 1
    )


async def test_commands_for_another_bot_do_not_change_state(native):
    handler = UpdateHandler(
        native.bot,
        native.backend,
        await native.backend.configuration(),
        "test_her_bot",
        DurableAcknowledgements(),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(handler.router)
    update = Update.model_validate(
        {
            "update_id": 502,
            "message": {
                "message_id": 71,
                "date": int(datetime.now(UTC).timestamp()),
                "chat": {"id": OWNER, "type": "private"},
                "from": {"id": OWNER, "is_bot": False, "first_name": "Test"},
                "text": "/resume@another_bot",
            },
        }
    )
    await dispatcher.feed_update(native.bot, update)
    assert not await native.rows(
        "SELECT id FROM tbl_inboxes WHERE update_id=502"
    )
    assert not await native.rows("SELECT id FROM tbl_owner_actions")
    assert not native.services.model_requests


async def test_polling_acknowledges_only_durable_updates_and_records_coverage(
    native,
):
    acknowledgements = DurableAcknowledgements()
    native.bot.session.middleware(acknowledgements)
    native.bot.session.middleware(PollingHeartbeat(native.backend))
    acknowledgements.committed(511)
    acknowledgements.failed(510)
    await native.bot.get_updates(offset=512, timeout=0)
    assert int(native.services.telegram_requests[-1]["offset"]) == 510
    acknowledgements.committed(510)
    await native.bot.get_updates(offset=512, timeout=0)
    assert int(native.services.telegram_requests[-1]["offset"]) == 512
    coverage = await native.rows(
        "SELECT last_heartbeat_at FROM tbl_channel_coverages"
    )
    assert len(coverage) == 1 and coverage[0]["last_heartbeat_at"] is not None


async def test_owner_forward_imports_only_configured_channel_without_model(
    native,
):
    forwarded = ChannelPostWrite(
        channel_id=CHANNEL,
        message_id=900,
        posted_at=datetime.now(UTC),
        text="متن فورواردشده",
        origin="imported",
    )
    await native.post(
        message(521, "متن فورواردشده").model_copy(
            update={"forwarded_post": forwarded}
        )
    )
    await native.services.received(
        lambda r: "تاریخچهٔ مشاهده‌شده" in r.get("text", "")
    )
    assert await native.rows(
        "SELECT message_id,origin FROM tbl_channel_posts"
    ) == [{"message_id": 900, "origin": "imported"}]
    await native.post(
        message(522, "متن فورواردشده").model_copy(
            update={
                "forwarded_post": forwarded.model_copy(
                    update={"channel_id": -100999}
                )
            }
        )
    )
    assert len(await native.rows("SELECT id FROM tbl_channel_posts")) == 1
    assert not native.services.model_requests
