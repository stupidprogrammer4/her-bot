import asyncio
from datetime import UTC, date, datetime, time, timedelta

import pytest
from amupouya_calendar.models import CalendarEntry, CalendarPolicy

from her_api.modules.content.occasions.domain.dtos import (
    OccasionUpdate,
    OccasionWrite,
)
from her_api.modules.content.occasions.interfaces import (
    IOccasionQueries,
    IOccasionService,
)
from her_api.modules.ops.settings.interfaces import ISettingsService
from her_api.modules.publishing.plans.interfaces import IPlanCommands
from her_contracts.policy import AccessPolicy, OccasionPolicy, WindowPolicy
from tests.conftest import CHANNEL

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def settings_for_occasions(native, policy: OccasionPolicy) -> None:
    async with native.scope() as scope:
        service = await scope.get(ISettingsService)
        current = await service.get("window")
        await service.write(
            "window",
            WindowPolicy(
                timezone="UTC",
                start=time(0),
                end=time(23, 59),
                text_min=0,
                text_max=0,
            ),
            current.revision,
        )
        current = await service.get("occasions")
        await service.write("occasions", policy, current.revision)


async def create_test_day(native, today: date) -> CalendarEntry:
    entry = CalendarEntry(
        id="test-girls",
        title="روز دختر آزمایشی",
        calendar="Gregorian",
        type="International",
        rule="single event",
        year=today.year,
        month=today.month,
        day=today.day,
        source="test-calendar",
        status="custom",
        tags=["test-girls"],
    )
    async with native.scope() as scope:
        service = await scope.get(IOccasionService)
        await service.create(OccasionWrite(entry=entry))
    return entry


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_db_edits_survive_reseed_and_change_the_consumed_day(native):
    async with native.scope() as scope:
        queries = await scope.get(IOccasionQueries)
        original = await queries.day(
            date(2026, 10, 11), CalendarPolicy(tags=["girls"]), "Asia/Tehran"
        )
        girl = next(
            e for e in original.events if e.title == "روز جهانی دختران"
        )
        assert girl.status == "official"
        unrelated = await queries.day(
            date(2026, 2, 21),
            CalendarPolicy(tags=["women", "girls", "motherhood"]),
            "Asia/Tehran",
        )
        assert unrelated.events == []
        girlfriend = await queries.day(
            date(2026, 8, 1),
            CalendarPolicy(tags=["relationship"]),
            "Asia/Tehran",
        )
        assert any(
            e.status == "unofficial" and "دوست‌دختر" in e.title
            for e in girlfriend.events
        )
        service = await scope.get(IOccasionService)
        row = await service.get(girl.id)
        changed = await service.update(
            girl.id,
            OccasionUpdate(
                entry=row.entry.model_copy(
                    update={"title": "عنوان ویرایش‌شده"}
                ),
                revision=row.revision,
                enabled=False,
            ),
        )
        with pytest.raises(ValueError, match="changed"):
            await service.update(girl.id, row)
        assert changed.revision == row.revision + 1
        await service.seed()
    async with native.scope() as scope:
        queries = await scope.get(IOccasionQueries)
        after = await queries.day(
            date(2026, 10, 11), CalendarPolicy(tags=["girls"]), "Asia/Tehran"
        )
        assert girl.id not in {e.id for e in after.events}
        service = await scope.get(IOccasionService)
        saved = await service.get(girl.id)
        assert not saved.enabled and saved.entry.title == "عنوان ویرایش‌شده"
        page = await service.search("عنوان ویرایش‌شده", 1, 20)
        assert page.total == 1 and page.items[0] == saved


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_concurrent_plans_and_replay_create_one_dated_occasion(native):
    now = datetime.now(UTC).replace(microsecond=0)
    native.clock.instant = now
    await create_test_day(native, now.date())
    await settings_for_occasions(
        native,
        OccasionPolicy(
            tags=["test-girls"], time=time(0), catchup_until=time(23, 59)
        ),
    )

    async def plan():
        async with native.scope() as scope:
            commands = await scope.get(IPlanCommands)
            result = await commands.prepare()
            return result

    await asyncio.gather(plan(), plan())
    await plan()
    rows = await native.rows(
        "SELECT id,occasion_json,scheduled_at,deadline_at "
        "FROM tbl_publication_jobs WHERE kind='occasion'"
    )
    assert (
        len(rows) == 1 and now.date().isoformat() in rows[0]["occasion_json"]
    )
    assert rows[0]["deadline_at"].date() == now.date()
    # Civil-day occasions cannot spill into the next operational day.
    native.clock.instant = datetime.combine(
        now.date() + timedelta(days=1), time(0, 30), UTC
    )
    await plan()
    assert (
        len(
            await native.rows(
                "SELECT id FROM tbl_publication_jobs WHERE kind='occasion'"
            )
        )
        == 1
    )


async def test_scheduler_prepares_and_worker_sends_one_occasion(native):
    today = datetime.now(UTC).date()
    entry = await create_test_day(native, today)
    caption = "امروز " + entry.title + "ه؛ این گوشه برای خودمونه 🎀🤍"
    native.services.model_replies = [{"role": "assistant", "content": caption}]
    await settings_for_occasions(
        native,
        OccasionPolicy(
            tags=["test-girls"], time=time(0), catchup_until=time(23, 59)
        ),
    )
    async with native.scope() as scope:
        settings = await scope.get(ISettingsService)
        access = await settings.get("access")
        assert isinstance(access.value, AccessPolicy)
        await settings.write(
            "access",
            access.value.model_copy(update={"paused": False}),
            access.revision,
        )
    sent = await native.services.received(
        lambda r: (
            int(r.get("chat_id", 0)) == CHANNEL and r.get("text") == caption
        )
    )
    assert int(sent["chat_id"]) == CHANNEL
    from tests.test_publishing import dispatch

    job_ids = await native.rows(
        "SELECT id FROM tbl_publication_jobs WHERE kind='occasion'"
    )
    await dispatch(job_ids[0]["id"])
    rows = await native.rows(
        "SELECT id,status,text,occasion_json "
        "FROM tbl_publication_jobs WHERE kind='occasion'"
    )
    assert (
        len(rows) == 1
        and rows[0]["status"] == "sent"
        and rows[0]["text"] == caption
    )
    assert entry.title in rows[0]["occasion_json"]
    # Replaying the actual delivery task must not send a second channel post.
    await dispatch(rows[0]["id"])
    assert (
        len(
            [
                r
                for r in native.services.telegram_requests
                if r.get("text") == caption
            ]
        )
        == 1
    )
