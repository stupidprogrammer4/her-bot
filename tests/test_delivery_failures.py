from datetime import UTC, datetime, timedelta

import pytest

from her_api.modules.ops.settings.interfaces import ISettingsService
from her_contracts.policy import AccessPolicy
from tests.test_publishing import dispatch, seed_job, upload

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_queued_replay_respects_future_retry_time(native):
    job = await seed_job(
        native,
        text="ارسال با تأخیر محدودیت تلگرام",
        next_attempt_at=datetime.now(UTC) + timedelta(seconds=60),
    )
    await dispatch(job)
    assert not any(
        request.get("text") == "ارسال با تأخیر محدودیت تلگرام"
        for request in native.services.telegram_requests
    )
    rows = await native.rows(
        "SELECT status,attempts FROM tbl_publication_jobs WHERE id=:id",
        {"id": job},
    )
    assert rows == [{"status": "pending", "attempts": 0}]


async def test_automatic_audio_deadline_reaches_gateway_and_sends(native):
    track = await upload(native, "deadline")
    async with native.scope() as scope:
        service = await scope.get(ISettingsService)
        access = await service.get("access")
        assert isinstance(access.value, AccessPolicy)
        await service.write(
            "access",
            access.value.model_copy(update={"paused": False}),
            access.revision,
        )
    job = await seed_job(
        native,
        kind="music",
        track_id=track,
        automatic=True,
        text="کپشن آمادهٔ آهنگ",
        deadline_at=datetime.now(UTC) + timedelta(minutes=2),
    )
    await dispatch(job)
    audio = await native.services.received(
        lambda request: request.get("caption") == "کپشن آمادهٔ آهنگ"
    )
    assert audio["audio"] == "file-deadline"


async def test_permanent_failure_and_recovery_alert_owner_without_retry(
    native,
):
    native.services.telegram_errors["خطای قطعی آزمون"] = {
        "ok": False,
        "error_code": 403,
        "description": "blocked",
        "http_status": 403,
    }
    job = await seed_job(native, text="خطای قطعی آزمون")
    await dispatch(job)
    await native.services.received(
        lambda request: (
            "ارسال قطعی نشده" in request.get("text", "")
            and ("کار: " + str(job)) in request.get("text", "")
        )
    )
    await dispatch(job)
    assert (
        len(
            [
                r
                for r in native.services.telegram_requests
                if r.get("text") == "خطای قطعی آزمون"
            ]
        )
        == 1
    )
    rows = await native.rows(
        "SELECT status,attempts FROM tbl_publication_jobs WHERE id=:id",
        {"id": job},
    )
    assert rows == [{"status": "failed", "attempts": 1}]
