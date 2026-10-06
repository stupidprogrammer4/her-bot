import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from her_api.modules.ops.settings.interfaces import ISettingsService
from her_api.modules.publishing.deliveries.tasks.schedulers.prepare import (
    PreparePublication,
)
from her_contracts.policy import AccessPolicy
from tests.conftest import CHANNEL, OWNER
from tests.test_publishing import dispatch, seed_job

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_delivery_does_not_generate_or_send_unprepared_text(native):
    job = await seed_job(native, text=None, topic="music")
    await dispatch(job)
    assert not native.services.model_requests
    assert not any(
        int(request.get("chat_id", 0)) == CHANNEL
        for request in native.services.telegram_requests
    )
    rows = await native.rows(
        "SELECT status,text,attempts FROM tbl_publication_jobs WHERE id=:id",
        {"id": job},
    )
    assert rows == [{"status": "pending", "text": None, "attempts": 0}]


async def prepare(job_id: int) -> None:
    task = await PreparePublication.enqueue(job_id)
    result = await task.wait_result(timeout=15)
    assert not result.is_err, str(result.error)


async def test_future_text_is_persisted_then_scheduler_sends_without_model(
    native,
):
    future = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=1)
    caption = "گربه‌ها فکر می‌کنن صاحب خونه‌ان؛ شاید هم درست می‌گن 🎀"
    native.services.model_replies = [{"role": "assistant", "content": caption}]
    job = await seed_job(
        native,
        text=None,
        topic="cats",
        automatic=False,
        scheduled_at=future,
        next_attempt_at=future,
        deadline_at=future + timedelta(minutes=5),
    )
    await prepare(job)
    stored = await native.rows(
        "SELECT status,text,scheduled_at,attempts "
        "FROM tbl_publication_jobs WHERE id=:id",
        {"id": job},
    )
    assert stored[0]["status"] == "pending"
    assert stored[0]["text"] == caption
    assert stored[0]["scheduled_at"] == future.replace(
        tzinfo=None, microsecond=0
    )
    assert stored[0]["attempts"] == 0
    assert not any(
        int(request.get("chat_id", 0)) == CHANNEL
        for request in native.services.telegram_requests
    )
    native.services.model_status = 402
    await native.execute(
        "UPDATE tbl_publication_jobs "
        "SET scheduled_at=:now,next_attempt_at=:now WHERE id=:id",
        {"id": job, "now": datetime.now(UTC)},
    )
    sent = await native.services.received(
        lambda request: request.get("text") == caption
    )
    assert int(sent["chat_id"]) == CHANNEL
    await native.services.received(
        lambda request: (
            "فرستادم" in request.get("text", "")
            and int(request.get("chat_id", 0)) == OWNER
        )
    )
    assert len(native.services.model_requests) == 1
    assert (
        await native.rows(
            "SELECT status,text FROM tbl_publication_jobs WHERE id=:id",
            {"id": job},
        )
    ) == [{"status": "sent", "text": caption}]


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_concurrent_preparation_and_replay_keep_one_saved_text(native):
    future = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=1)
    job = await seed_job(
        native, text=None, scheduled_at=future, next_attempt_at=future
    )
    await asyncio.gather(prepare(job), prepare(job))
    saved = await native.rows(
        "SELECT status,text,scheduled_at FROM tbl_publication_jobs "
        "WHERE id=:id",
        {"id": job},
    )
    assert saved[0]["status"] == "pending" and saved[0]["text"]
    await prepare(job)
    assert len(native.services.model_requests) == 1
    assert saved == await native.rows(
        "SELECT status,text,scheduled_at FROM tbl_publication_jobs "
        "WHERE id=:id",
        {"id": job},
    )
    assert not any(
        int(request.get("chat_id", 0)) == CHANNEL
        for request in native.services.telegram_requests
    )


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_paused_automatic_slot_is_prepared_only_after_resume(native):
    future = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=1)
    job = await seed_job(
        native,
        text=None,
        automatic=True,
        scheduled_at=future,
        next_attempt_at=future,
    )
    await prepare(job)
    assert not native.services.model_requests
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        access = await settings.get("access")
        assert isinstance(access.value, AccessPolicy)
        await settings.write(
            "access",
            access.value.model_copy(update={"paused": False}),
            access.revision,
        )
    await prepare(job)
    saved = await native.rows(
        "SELECT status,text,scheduled_at FROM tbl_publication_jobs "
        "WHERE id=:id",
        {"id": job},
    )
    assert saved[0]["status"] == "pending" and saved[0]["text"]
    assert saved[0]["scheduled_at"] == future.replace(tzinfo=None)
    assert len(native.services.model_requests) == 1
    assert not any(
        int(request.get("chat_id", 0)) == CHANNEL
        for request in native.services.telegram_requests
    )
