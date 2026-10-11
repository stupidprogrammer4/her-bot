import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from her_api.modules.ops.settings.interfaces import ISettingsService
from her_api.modules.publishing.plans.interfaces import IPlanCommands
from her_contracts.policy import PersonaPolicy, WindowPolicy
from tests.test_prepared_publishing import prepare
from tests.test_publishing import dispatch, seed_job, upload

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_music_uses_only_the_saved_emoji_without_model_calls(native):
    track = await upload(native, "emoji")
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        persona = await settings.get("persona")
        assert isinstance(persona.value, PersonaPolicy)
        await settings.write(
            "persona",
            persona.value.model_copy(update={"music_emoji": "🎀"}),
            persona.revision,
        )
    job = await seed_job(
        native,
        kind="music",
        track_id=track,
        text=None,
        scheduled_at=datetime.now(UTC) - timedelta(seconds=1),
        next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    await prepare(job)
    await dispatch(job)
    sent = await native.services.received(
        lambda r: r.get("audio") == "file-emoji"
    )
    assert sent["caption"] == "🎀"
    assert not native.services.model_requests
    rows = await native.rows(
        "SELECT status,text,message_id FROM tbl_publication_jobs WHERE id=:id",
        {"id": job},
    )
    assert rows[0]["status"] == "sent" and rows[0]["message_id"]
    assert rows[0]["text"] == "🎀"


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_plan_uses_fewer_than_three_new_tracks_and_never_recycles(
    native,
):
    tracks = await asyncio.gather(
        *(upload(native, name) for name in ("old", "a", "b"))
    )
    await seed_job(
        native,
        kind="music",
        track_id=tracks[0],
        status="sent",
        sent_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    native.clock.instant = datetime(2026, 10, 12, 13, tzinfo=UTC)
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        policy = await settings.get("window")
        await settings.write(
            "window", WindowPolicy(text_min=0, text_max=0), policy.revision
        )
        plan = await (await scope.get(IPlanCommands)).prepare()
    rows = await native.rows(
        "SELECT track_id,kind FROM tbl_publication_jobs WHERE plan_id=:id",
        {"id": plan.id},
    )
    assert len(rows) == 2
    assert {r["track_id"] for r in rows} == set(tracks[1:])
    assert all(r["kind"] == "music" for r in rows)
    await native.execute(
        "UPDATE tbl_publication_jobs SET status='sent',sent_at=:now "
        "WHERE plan_id=:id",
        {"id": plan.id, "now": native.clock.now()},
    )
    native.clock.instant += timedelta(days=1)
    async with native.scope() as scope:
        tomorrow = await (await scope.get(IPlanCommands)).prepare()
    assert not await native.rows(
        "SELECT id FROM tbl_publication_jobs WHERE plan_id=:id",
        {"id": tomorrow.id},
    )
    assert tomorrow.music_status == "waiting_for_tracks"


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_concurrent_jobs_send_one_audio_and_skip_the_duplicate(native):
    track = await upload(native, "once")
    jobs = await asyncio.gather(
        *(
            seed_job(
                native,
                kind="music",
                track_id=track,
                text="Legacy explanation",
                scheduled_at=datetime.now(UTC) - timedelta(seconds=1),
                next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
            )
            for _ in range(2)
        )
    )
    await asyncio.gather(*(dispatch(job) for job in jobs))
    await native.execute(
        "UPDATE tbl_publication_jobs SET next_attempt_at=:now "
        "WHERE status='pending'",
        {"now": datetime.now(UTC) - timedelta(seconds=1)},
    )
    await asyncio.gather(*(dispatch(job) for job in jobs))
    requests = [
        r
        for r in native.services.telegram_requests
        if r.get("audio") == "file-once"
    ]
    assert len(requests) == 1 and requests[0]["caption"] == "🕯️"
    rows = await native.rows(
        "SELECT status,message_id FROM tbl_publication_jobs "
        "WHERE kind='music' ORDER BY status"
    )
    assert [r["status"] for r in rows] == ["sent", "skipped"]
    assert rows[0]["message_id"] and rows[1]["message_id"] is None


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_uncertain_audio_is_not_automatically_sent_again(native):
    track = await upload(native, "uncertain")
    await seed_job(
        native, kind="music", track_id=track, status="delivery_unknown"
    )
    job = await seed_job(
        native,
        kind="music",
        track_id=track,
        scheduled_at=datetime.now(UTC) - timedelta(seconds=1),
        next_attempt_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    await dispatch(job)
    assert not any(r.get("audio") for r in native.services.telegram_requests)
    rows = await native.rows(
        "SELECT status FROM tbl_publication_jobs WHERE id=:id", {"id": job}
    )
    assert rows == [{"status": "skipped"}]
