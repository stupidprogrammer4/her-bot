import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from papilio.infra.db.transaction import transaction

from her_api.modules.library.tracks.domain.dtos import TrackChange
from her_api.modules.library.tracks.interfaces import ITrackService
from her_api.modules.ops.settings.interfaces import ISettingsService
from her_api.modules.publishing.deliveries.domain.models import (
    PublicationJobModel,
)
from her_api.modules.publishing.deliveries.infra.mysql import (
    PublicationRepository,
)
from her_api.modules.publishing.deliveries.interfaces import (
    IPublicationCommands,
)
from her_api.modules.publishing.deliveries.tasks.schedulers.deliver import (
    Deliver,
)
from her_api.modules.publishing.plans.interfaces import (
    IPlanCommands,
)
from her_contracts.media import AudioUpload
from her_contracts.policy import PersonaPolicy, WindowPolicy
from tests.conftest import BOT_ID, CHANNEL, GROUP, OWNER
from tests.messages import message

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def upload(native, unique: str) -> int:
    async with native.scope() as scope:
        tracks = await scope.get(ITrackService)
        result = await tracks.upload(
            AudioUpload(
                bot_id=BOT_ID,
                file_id="file-" + unique,
                file_unique_id="unique-" + unique,
                source_chat_id=OWNER,
                source_message_id=10,
                title="آهنگ " + unique,
                duration=120,
            )
        )
        return result.id


async def seed_job(native, **changes) -> int:
    now = datetime.now(UTC)
    data = {
        "kind": "text",
        "channel_id": CHANNEL,
        "owner_id": OWNER,
        "automatic": False,
        "scheduled_at": now,
        "next_attempt_at": now,
        "text": "متن آزمون عمومی",
    } | changes
    async with native.scope() as scope:
        repo = await scope.get(PublicationRepository)
        async with transaction():
            job = await repo.create(PublicationJobModel(**data))
        return job.id


async def dispatch(job_id: int) -> None:
    task = await Deliver.enqueue(job_id)
    result = await task.wait_result(timeout=15)
    assert not result.is_err, str(result.error)


async def test_owner_greeting_works_paused_without_tracks_and_model(native):
    native.services.model_status = 402
    await native.post(message(101, "شمع زیبا به بچه‌ها سلام کن"))
    greeted = await native.services.received(
        lambda r: (
            int(r.get("chat_id", 0)) == CHANNEL
            and "سلام بچه‌هاا" in r.get("text", "")
        )
    )
    assert "شمع زیبام" in greeted["text"]
    # The completion notification can only be queued after the ledger commits.
    await native.services.received(
        lambda r: (
            int(r.get("chat_id", 0)) == OWNER
            and "فرستادم" in r.get("text", "")
        )
    )
    rows = await native.rows(
        (
            "SELECT status,message_id FROM "
            "tbl_publication_jobs WHERE update_id=101 AND "
            "write_slot=1"
        )
    )
    assert (
        len(rows) == 1
        and rows[0]["status"] == "sent"
        and rows[0]["message_id"] > 0
    )
    assert not native.services.model_requests
    await native.post(message(101, "شمع زیبا به بچه‌ها سلام کن"))
    assert (
        len(
            await native.rows(
                (
                    "SELECT id FROM tbl_publication_jobs WHERE "
                    "update_id=101 AND write_slot=1"
                )
            )
        )
        == 1
    )


async def test_owner_group_greeting_works_with_member_chat_disabled(native):
    data = message(102, "شمع زیبا به بچه‌ها سلام کن").model_copy(
        update={"chat_id": GROUP, "chat_type": "supergroup"}
    )
    await native.post(data)
    await native.services.received(
        lambda r: (
            int(r.get("chat_id", 0)) == GROUP
            and "سلام بچه‌هاا" in r.get("text", "")
        )
    )
    await native.services.received(
        lambda r: (
            int(r.get("chat_id", 0)) == OWNER
            and "فرستادم" in r.get("text", "")
        )
    )
    assert (
        len(
            [
                r
                for r in native.services.telegram_requests
                if int(r.get("chat_id", 0)) == GROUP
            ]
        )
        == 1
    )


async def test_archive_refreshes_file_id_and_preview_uses_model_fallback(
    native,
):
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        persona = await settings.get("persona")
        assert isinstance(persona.value, PersonaPolicy)
        await settings.write(
            "persona",
            persona.value.model_copy(update={"music_fallbacks": {}}),
            persona.revision,
        )
    track = await upload(native, "a")
    async with native.scope() as scope:
        service = await scope.get(ITrackService)
        again = await service.upload(
            AudioUpload(
                bot_id=BOT_ID,
                file_id="refreshed-file",
                file_unique_id="unique-a",
                source_chat_id=OWNER,
                source_message_id=11,
                title="بازنشر",
                duration=121,
            )
        )
    assert again.id == track
    native.services.model_status = 402
    await native.post(message(103, "/preview " + str(track)))
    sent = await native.services.received(
        lambda r: r.get("method") == "sendAudio"
    )
    assert sent["audio"] == "refreshed-file"
    assert sent["caption"] == "اینم برای امشب 🎧"
    assert int(sent["chat_id"]) == OWNER
    assert "parse_mode" not in sent


async def test_plan_survives_replanning_and_range_changes(
    native,
):
    await asyncio.gather(
        upload(native, "a"),
        upload(native, "b"),
        upload(native, "c"),
        upload(native, "d"),
    )
    native.clock.instant = datetime(2026, 10, 8, 13, tzinfo=UTC)
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        current = await settings.get("window")
        await settings.write(
            "window", WindowPolicy(text_min=1, text_max=5), current.revision
        )
        plans = await scope.get(IPlanCommands)
        plan = await plans.prepare()
        plan_id = plan.id
    original = await native.rows(
        (
            "SELECT id,kind,track_id,scheduled_at,topic FROM "
            "tbl_publication_jobs WHERE plan_id=:plan AND "
            "kind IN ('music','text') ORDER BY kind,id"
        ),
        {"plan": plan_id},
    )
    music = [r for r in original if r["kind"] == "music"]
    texts = [r for r in original if r["kind"] == "text"]
    assert len(music) == 3 and len({r["track_id"] for r in music}) == 3
    assert 1 <= len(texts) <= 5
    assert len({r["scheduled_at"] for r in music}) == 3
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        current = await settings.get("window")
        await settings.write(
            "window", WindowPolicy(text_min=0, text_max=0), current.revision
        )
        plans = await scope.get(IPlanCommands)
        same = await plans.prepare()
    assert same.id == plan_id
    assert original == await native.rows(
        (
            "SELECT id,kind,track_id,scheduled_at,topic FROM "
            "tbl_publication_jobs WHERE plan_id=:plan AND "
            "kind IN ('music','text') ORDER BY kind,id"
        ),
        {"plan": plan_id},
    )


async def test_music_shortage_and_disabled_track_keep_text_and_slot_time(
    native,
):
    native.clock.instant = datetime(2026, 10, 8, 13, tzinfo=UTC)
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        window = await settings.get("window")
        await settings.write(
            "window", WindowPolicy(text_min=2, text_max=2), window.revision
        )
        plans = await scope.get(IPlanCommands)
        waiting = await plans.prepare()
    assert waiting.music_status == "waiting_for_tracks"
    rows = await native.rows(
        "SELECT kind FROM tbl_publication_jobs WHERE plan_id=:plan",
        {"plan": waiting.id},
    )
    assert len([r for r in rows if r["kind"] == "text"]) == 2
    assert len([r for r in rows if r["kind"] == "music"]) == 0
    await upload(native, "a")
    await upload(native, "b")
    await upload(native, "c")
    await upload(native, "d")
    async with native.scope() as scope:
        plans = await scope.get(IPlanCommands)
        planned = await plans.prepare()
    before = await native.rows(
        (
            "SELECT id,track_id,scheduled_at FROM "
            "tbl_publication_jobs WHERE plan_id=:plan AND "
            "kind='music' ORDER BY id"
        ),
        {"plan": planned.id},
    )
    async with native.scope() as scope:
        tracks = await scope.get(ITrackService)
        await tracks.change(before[0]["track_id"], TrackChange(active=False))
        plans = await scope.get(IPlanCommands)
        await plans.prepare()
    after = await native.rows(
        (
            "SELECT id,track_id,scheduled_at FROM "
            "tbl_publication_jobs WHERE plan_id=:plan AND "
            "kind='music' ORDER BY id"
        ),
        {"plan": planned.id},
    )
    assert (
        before[0]["id"] == after[0]["id"]
        and before[0]["scheduled_at"] == after[0]["scheduled_at"]
    )
    assert before[0]["track_id"] != after[0]["track_id"]
    assert len({r["track_id"] for r in after}) == 3


async def test_concurrent_delivery_and_unknown_result_do_not_duplicate(
    native,
):
    job = await seed_job(native, text="پیام تنها")
    await asyncio.gather(dispatch(job), dispatch(job))
    await native.services.received(
        lambda request: request.get("text") == "پیام تنها"
    )
    await native.services.received(
        lambda request: (
            "فرستادم" in request.get("text", "")
            and int(request.get("chat_id", 0)) == OWNER
        )
    )
    assert (
        len(
            [
                r
                for r in native.services.telegram_requests
                if r.get("text") == "پیام تنها"
            ]
        )
        == 1
    )
    assert (
        await native.rows(
            "SELECT status FROM tbl_publication_jobs WHERE id=:id", {"id": job}
        )
    )[0]["status"] == "sent"
    native.services.telegram_errors["نتیجه نامشخص"] = {
        "ok": False,
        "error_code": 500,
        "description": "uncertain",
        "http_status": 500,
    }
    unknown = await seed_job(native, text="نتیجه نامشخص")
    await dispatch(unknown)
    await dispatch(unknown)
    await native.services.received(lambda r: r.get("text") == "نتیجه نامشخص")
    await native.services.received(
        lambda r: (
            "ارسال قطعی نشده" in r.get("text", "")
            and ("کار: " + str(unknown)) in r.get("text", "")
        )
    )
    assert (
        len(
            [
                r
                for r in native.services.telegram_requests
                if r.get("text") == "نتیجه نامشخص"
            ]
        )
        == 1
    )
    assert (
        await native.rows(
            "SELECT status FROM tbl_publication_jobs WHERE id=:id",
            {"id": unknown},
        )
    )[0]["status"] == "delivery_unknown"


async def test_recovery_does_not_send_expired_or_uncertain_jobs(
    native,
):
    now = datetime.now(UTC)
    expired = await seed_job(
        native, automatic=True, deadline_at=now - timedelta(seconds=1)
    )
    interrupted = await seed_job(
        native,
        status="sending",
        lease_expires_at=now - timedelta(seconds=1),
        text="قطع شده",
    )
    preparing = await seed_job(
        native,
        status="preparing",
        lease_expires_at=now - timedelta(seconds=1),
        scheduled_at=now + timedelta(hours=1),
        next_attempt_at=now + timedelta(hours=1),
    )
    async with native.scope() as scope:
        pub = await scope.get(IPublicationCommands)
        await pub.recover()
    states = await native.rows(
        "SELECT id,status FROM tbl_publication_jobs WHERE id IN (:a,:b,:c)",
        {"a": expired, "b": interrupted, "c": preparing},
    )
    assert {r["id"]: r["status"] for r in states} == {
        expired: "expired",
        interrupted: "delivery_unknown",
        preparing: "pending",
    }
    await asyncio.gather(dispatch(expired), dispatch(interrupted))
    assert not any(
        r.get("text") in {"متن آزمون عمومی", "قطع شده"}
        for r in native.services.telegram_requests
    )
