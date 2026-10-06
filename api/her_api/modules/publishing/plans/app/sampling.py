from datetime import UTC, date, datetime, timedelta
from random import SystemRandom
from zoneinfo import ZoneInfo

from her_api.modules.library.tracks.domain.dtos import TrackCandidate
from her_api.shared.dates import as_utc
from her_contracts.policy import WindowPolicy


class WindowSampler:
    def __init__(self, rng: SystemRandom):
        self.rng = rng

    def operational_window(
        self, now: datetime, policy: WindowPolicy
    ) -> tuple[date, datetime, datetime, bool]:
        if now.tzinfo is None:
            raise ValueError("Clock must be timezone-aware")
        zone = ZoneInfo(policy.timezone)
        local = now.astimezone(zone)
        day = local.date()
        opening = (
            policy.text_start
            if policy.text_start is not None
            else policy.start
        )
        crosses_midnight = policy.end < opening
        if crosses_midnight and local.time().replace(tzinfo=None) < policy.end:
            day -= timedelta(days=1)
        start = datetime.combine(day, opening, zone).astimezone(UTC)
        end_day = day + timedelta(days=1) if crosses_midnight else day
        end = datetime.combine(end_day, policy.end, zone).astimezone(UTC)
        if now >= end:
            day += timedelta(days=1)
            start = datetime.combine(day, opening, zone).astimezone(UTC)
            end = datetime.combine(
                day + timedelta(days=int(crosses_midnight)), policy.end, zone
            ).astimezone(UTC)
        return day, start, end, start < now < end

    def music_start(self, day: date, policy: WindowPolicy) -> datetime:
        return datetime.combine(
            day, policy.start, ZoneInfo(policy.timezone)
        ).astimezone(UTC)

    def times(
        self, start: datetime, end: datetime, count: int
    ) -> list[datetime]:
        seconds = int((end - start).total_seconds())
        if count > seconds or seconds <= 0:
            raise ValueError("Window too short")
        return [
            start + timedelta(seconds=n)
            for n in sorted(self.rng.sample(range(seconds), count))
        ]

    def tracks(
        self,
        candidates: list[TrackCandidate],
        count: int,
        cutoff: datetime,
        exclude: set[int] | None = None,
    ) -> list[int]:
        rows = [
            row for row in candidates if row.track.id not in (exclude or set())
        ]
        self.rng.shuffle(rows)
        rows.sort(
            key=lambda c: (
                c.last_played is not None and as_utc(c.last_played) >= cutoff,
                as_utc(c.last_played).timestamp()
                if c.last_played
                else float("-inf"),
            )
        )
        return [r.track.id for r in rows[:count]]

    def topics(
        self, topics: list[str], count: int, previous: set[str]
    ) -> list[str]:
        preferred = [t for t in topics if t not in previous] or topics
        return [self.rng.choice(preferred) for _ in range(count)]
