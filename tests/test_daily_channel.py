import asyncio
from datetime import UTC, datetime, time, timedelta

import pytest

from her_api.modules.library.tracks.domain.dtos import TrackChange
from her_api.modules.library.tracks.interfaces import ITrackService
from her_api.modules.ops.settings.interfaces import ISettingsService
from her_api.modules.persona.privacy.app.defaults import initial_persona
from her_api.modules.publishing.plans.interfaces import (
    IPlanCommands,
    IPlanQueries,
)
from her_contracts.media import AudioUpload, Mood
from her_contracts.policy import PersonaPolicy, WindowPolicy
from tests.conftest import BOT_ID, OWNER
from tests.messages import message
from tests.test_prepared_publishing import prepare
from tests.test_publishing import seed_job, upload

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_daytime_plan_keeps_music_in_evening_and_preserves_slots(native):
    await asyncio.gather(*(upload(native, name) for name in ("a", "b", "c")))
    native.clock.instant = datetime(2026, 10, 8, 5, tzinfo=UTC)
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        current = await settings.get("window")
        await settings.write(
            "window",
            WindowPolicy(text_start=time(9), text_min=5, text_max=5),
            current.revision,
        )
        plans = await scope.get(IPlanCommands)
        plan = await plans.prepare()
        queries = await scope.get(IPlanQueries)
        current_plan, jobs = await queries.current()
        assert current_plan is not None and current_plan.id == plan.id
        assert len([job for job in jobs if job.kind == "text"]) == 5
    stored = await native.rows(
        "SELECT starts_at,text_starts_at,ends_at FROM tbl_plans WHERE id=:id",
        {"id": plan.id},
    )
    assert stored == [
        {
            "starts_at": datetime(2026, 10, 8, 14, 30),
            "text_starts_at": datetime(2026, 10, 8, 5, 30),
            "ends_at": datetime(2026, 10, 8, 22, 30),
        }
    ]
    original = await native.rows(
        "SELECT id,kind,scheduled_at FROM tbl_publication_jobs "
        "WHERE plan_id=:id AND kind IN ('text','music') ORDER BY id",
        {"id": plan.id},
    )
    assert len(original) == 8
    assert all(
        datetime(2026, 10, 8, 5, 30)
        <= row["scheduled_at"]
        < datetime(2026, 10, 8, 22, 30)
        for row in original
        if row["kind"] == "text"
    )
    assert all(
        datetime(2026, 10, 8, 14, 30)
        <= row["scheduled_at"]
        < datetime(2026, 10, 8, 22, 30)
        for row in original
        if row["kind"] == "music"
    )
    native.clock.instant = datetime(2026, 10, 8, 7, tzinfo=UTC)
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        current = await settings.get("window")
        await settings.write("window", WindowPolicy(), current.revision)
        plans = await scope.get(IPlanCommands)
        assert (await plans.prepare()).id == plan.id
    assert original == await native.rows(
        "SELECT id,kind,scheduled_at FROM tbl_publication_jobs "
        "WHERE plan_id=:id AND kind IN ('text','music') ORDER BY id",
        {"id": plan.id},
    )


async def preview_mood(native, mood: Mood, update_id: int):
    async with native.scope() as scope:
        tracks = await scope.get(ITrackService)
        track = await tracks.upload(
            AudioUpload(
                bot_id=BOT_ID,
                file_id="audio-" + mood,
                file_unique_id="unique-" + mood,
                source_chat_id=OWNER,
                source_message_id=update_id,
                mood=mood,
                duration=120,
            )
        )
    await native.post(message(update_id, "/preview " + str(track.id)))
    try:
        sent = await native.services.received(
            lambda request: request.get("audio") == "audio-" + mood,
            timeout=30,
        )
    except TimeoutError:
        jobs = await native.rows(
            "SELECT id,kind,text,status,failure_reason,next_attempt_at "
            "FROM tbl_publication_jobs ORDER BY id"
        )
        pytest.fail(
            f"Missing {mood} preview; jobs={jobs!r}; "
            f"requests={native.services.telegram_requests!r}"
        )
    assert sent["caption"] in initial_persona().music_fallbacks[mood]
    assert int(sent["chat_id"]) == OWNER


async def test_each_music_mood_has_a_saved_caption_during_model_outage(native):
    native.services.model_status = 402
    moods: list[Mood] = [
        "calm",
        "sad",
        "romantic",
        "energetic",
        "nostalgic",
        "neutral",
    ]
    await asyncio.gather(
        *(
            preview_mood(native, mood, 300 + index)
            for index, mood in enumerate(moods)
        )
    )
    saved = await native.rows(
        "SELECT t.mood,j.text,j.status,j.message_id FROM "
        "tbl_publication_jobs j "
        "JOIN tbl_tracks t ON j.track_id=t.id WHERE "
        "j.kind='preview' ORDER BY t.mood"
    )
    assert len(saved) == 6
    assert all(
        row["text"] in initial_persona().music_fallbacks[row["mood"]]
        for row in saved
    )


async def test_configured_caption_can_repeat_when_outage_choices_are_exhausted(
    native,
):
    native.scheduler.terminate()
    await native.scheduler.wait()
    native.services.model_status = 402
    track_id = await upload(native, "calm")
    caption = "این یکی برای چند دقیقه آروم‌تر بودن 🎧"
    async with native.scope() as scope:
        tracks = await scope.get(ITrackService)
        await tracks.change(track_id, TrackChange(mood="calm"))
        settings = await scope.get(ISettingsService)
        persona = await settings.get("persona")
        assert isinstance(persona.value, PersonaPolicy)
        await settings.write(
            "persona",
            persona.value.model_copy(
                update={"music_fallbacks": {"calm": [caption]}}
            ),
            persona.revision,
        )
    future = datetime.now(UTC) + timedelta(hours=1)
    first = await seed_job(
        native,
        kind="music",
        track_id=track_id,
        text=None,
        scheduled_at=future,
        next_attempt_at=future,
    )
    second = await seed_job(
        native,
        kind="music",
        track_id=track_id,
        text=None,
        scheduled_at=future,
        next_attempt_at=future,
    )
    await prepare(first)
    await prepare(second)
    rows = await native.rows(
        "SELECT text,status FROM tbl_publication_jobs "
        "WHERE id IN (:first,:second) ORDER BY id",
        {"first": first, "second": second},
    )
    assert rows == [{"text": caption, "status": "pending"}] * 2
    assert not any(
        request.get("method") == "sendAudio"
        for request in native.services.telegram_requests
    )
