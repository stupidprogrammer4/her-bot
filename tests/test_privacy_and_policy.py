import hashlib
from datetime import datetime, time, timedelta
from random import Random
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from her_api.modules.conversations.actions.app.capabilities import (
    OwnerCapabilities,
)
from her_api.modules.conversations.actions.domain.tools import (
    PublishTextArguments,
)
from her_api.modules.persona.privacy.app.guard import IdentityGuard
from her_api.modules.publishing.plans.app.sampling import WindowSampler
from her_bot.app.addressing import Addressing
from her_bot.app.updates import ImportBuffer
from her_contracts.policy import WindowPolicy


def guard() -> IdentityGuard:
    settings = SimpleNamespace(
        security=SimpleNamespace(
            identity_hashes=[hashlib.sha256("نامفرضی".encode()).hexdigest()]
        )
    )
    return IdentityGuard(settings)


@pytest.mark.parametrize(
    "value",
    [
        "نامفرضی",
        "نام فرضی",
        "نام\u200dفرضی",
        "نامفرضیم",
        "نامفرضی نام فرضی",
        "نام&#160;فرضی",
    ],
)
def test_identity_never_survives_normalization_or_overlapping_redaction(value):
    privacy = guard()
    assert privacy.contains(value)
    redacted = privacy.scrub("قبل " + value + " بعد")
    assert not privacy.contains(redacted)
    assert redacted.startswith("قبل ") and redacted.endswith(" بعد")
    with pytest.raises(ValueError):
        privacy.require_safe(value)


def test_unrelated_text_and_public_alias_are_preserved():
    text = "شمع زیبا، Her، سلام 🎀🍓"
    assert guard().scrub(text) == text


@pytest.mark.parametrize(
    "hour,minute,day,partial",
    [
        (17, 59, 6, False),
        (18, 0, 6, False),
        (23, 30, 6, True),
        (1, 59, 5, True),
        (2, 0, 6, False),
    ],
)
def test_operational_evening_crosses_midnight_and_excludes_two_am(
    hour, minute, day, partial
):
    sampler = WindowSampler(Random(42))
    now = datetime(2026, 10, 6, hour, minute, tzinfo=ZoneInfo("Asia/Tehran"))
    evening, start, end, is_partial = sampler.operational_window(
        now, WindowPolicy()
    )
    assert evening.day == day
    assert start.astimezone(ZoneInfo("Asia/Tehran")).hour == 18
    assert end.astimezone(ZoneInfo("Asia/Tehran")).hour == 2
    assert is_partial is partial
    assert end - start == timedelta(hours=8)


def test_uniform_seconds_are_distinct_and_have_no_required_spacing():
    sampler = WindowSampler(Random(2))
    start = datetime(2026, 10, 6, 18, tzinfo=ZoneInfo("Asia/Tehran"))
    times = sampler.times(start, start + timedelta(seconds=3), 3)
    assert times == [
        start,
        start + timedelta(seconds=1),
        start + timedelta(seconds=2),
    ]
    with pytest.raises(ValueError):
        sampler.operational_window(start.replace(tzinfo=None), WindowPolicy())


@pytest.mark.parametrize(
    "hour,day,partial",
    [(8, 6, False), (9, 6, False), (10, 6, True), (1, 5, True), (2, 6, False)],
)
def test_daily_text_window_and_music_share_the_operational_date(
    hour, day, partial
):
    sampler = WindowSampler(Random(42))
    policy = WindowPolicy(text_start=time(9))
    zone = ZoneInfo("Asia/Tehran")
    now = datetime(2026, 10, 6, hour, tzinfo=zone)
    operational_day, start, end, is_partial = sampler.operational_window(
        now, policy
    )
    assert operational_day.day == day
    assert start.astimezone(zone).hour == 9
    assert end - start == timedelta(hours=17)
    assert (
        sampler.music_start(operational_day, policy).astimezone(zone).hour
        == 18
    )
    assert is_partial is partial


@pytest.mark.parametrize("opening", [time(1), time(2), time(19)])
def test_text_opening_cannot_cross_into_another_operational_day(opening):
    with pytest.raises(ValidationError):
        WindowPolicy(text_start=opening)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("شمع زیبا سلام", True),
        ("شمع\u200cزیبا سلام", True),
        ("هرشمع زیبا سلام", False),
        ("Her سلام", True),
        ("there سلام", False),
        ("@example_her_bot سلام", True),
        ("@example_her_bot_extra سلام", False),
    ],
)
def test_aliases_have_word_boundaries(text, expected):
    assert (
        Addressing(["شمع زیبا", "Her"], "example_her_bot").addressed(
            text, replying_to_bot=False
        )
        is expected
    )


def test_owner_tools_refuse_arbitrary_destinations_and_unknown_fields():
    with pytest.raises(ValidationError):
        PublishTextArguments.model_validate(
            {"text": "سلام", "destination": "someone_else", "chat_id": 123}
        )
    with pytest.raises(ValidationError):
        PublishTextArguments.model_validate({"text": "سلام", "chat_id": 123})
    allowed = OwnerCapabilities().allowed("فقط پیش‌نویس بنویس و منتشر نکن")
    assert "publish_text" not in allowed


def test_import_buffer_refuses_overflow_before_writing():
    stream = ImportBuffer()
    stream.write(b"a" * (10 * 1024 * 1024))
    with pytest.raises(ValueError):
        stream.write(b"b")
    assert stream.getbuffer().nbytes == 10 * 1024 * 1024
