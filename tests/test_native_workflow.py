import json

import pytest

from tests.conftest import OWNER
from tests.messages import message


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_checks_native_mysql_and_redis(native):
    response = await native.http.get("/health")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_travels_through_native_worker_and_telegram(native):
    result = await native.post(message(100, "/start"))
    assert result["accepted"] and not result["replay"]
    request = await native.services.received(
        lambda r: (
            r.get("method") == "sendMessage"
            and "من شمع زیبام" in r.get("text", "")
        )
    )
    assert int(request["chat_id"]) == OWNER
    assert "parse_mode" not in request
    keyboard = json.loads(request["reply_markup"])["inline_keyboard"]
    assert any(
        "برگشت به خانه" in button["text"]
        and button["callback_data"] == "start"
        for row in keyboard
        for button in row
    )
    rows = await native.rows(
        "SELECT status FROM tbl_inboxes WHERE update_id=100"
    )
    assert rows == [{"status": "completed"}]
    replay = await native.post(message(100, "/start"))
    assert replay["replay"]
    jobs = await native.rows(
        "SELECT id FROM tbl_publication_jobs WHERE update_id=100"
    )
    assert len(jobs) == 1
