from datetime import datetime, timedelta

from papilio.infra.db.transaction import transaction

from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_api.modules.publishing.deliveries.domain.dtos import TrackReplacement
from her_api.modules.publishing.deliveries.domain.models import (
    PublicationJobModel,
)
from her_api.modules.publishing.deliveries.infra.mysql import (
    PublicationRepository,
)
from her_api.modules.publishing.deliveries.infra.readers import (
    PublicationReader,
)
from her_api.modules.publishing.plans.app.sampling import WindowSampler
from her_api.modules.publishing.plans.domain.models import PlanModel
from her_api.modules.publishing.plans.infra.mysql import PlanRepository
from her_api.shared.clock import Clock
from her_api.shared.dates import as_utc
from her_contracts.publications import PublicationKind


class PlanCommands:
    def __init__(
        self,
        plans: PlanRepository,
        jobs: PublicationRepository,
        reader: PublicationReader,
        settings: ISettingsQueries,
        sampler: WindowSampler,
        clock: Clock,
    ):
        self.clock = clock
        self.plans = plans
        self.jobs = jobs
        self.reader = reader
        self.settings = settings
        self.sampler = sampler

    async def prepare(self) -> PlanModel:
        settings = await self.settings.snapshot()
        now = self.clock.now()
        policy, access = settings.window, settings.access
        day, start, end, partial = self.sampler.evening(now, policy)
        plan = await self.plans.for_evening(access.channel_id, day)
        if (
            plan is None
            and partial
            and (end - now).total_seconds() < policy.bootstrap_min_seconds
        ):
            day, start, end, partial = self.sampler.evening(end, policy)
        async with transaction():
            if plan is None:
                plan = await self.plans.ensure(
                    PlanModel(
                        channel_id=access.channel_id,
                        evening_date=day,
                        starts_at=start,
                        ends_at=end,
                        text_min_snapshot=policy.text_min,
                        text_max_snapshot=policy.text_max,
                        bootstrap_partial=partial,
                    )
                )
            available_start = (
                max(
                    now.replace(microsecond=0) + timedelta(seconds=1),
                    as_utc(plan.starts_at),
                )
                if partial
                else as_utc(plan.starts_at)
            )
            end = as_utc(plan.ends_at)
            if available_start >= end:
                return plan.model_copy()
            previous = await self.reader.previous_topics(
                access.channel_id, day
            )
            candidates = await self.reader.track_candidates(access.channel_id)
            count = self.sampler.rng.randint(
                plan.text_min_snapshot, plan.text_max_snapshot
            )
            if plan.text_count is None and await self.plans.claim_text(
                plan.id, count, now
            ):
                times = self.sampler.times(available_start, end, count)
                topics = self.sampler.topics(
                    settings.persona.topics, count, previous
                )
                await self.jobs.create_many(
                    [
                        self._slot(
                            plan,
                            access.owner_id,
                            "text",
                            index + 1,
                            stamp,
                            end,
                            policy.grace_seconds,
                            topic=topic,
                        )
                        for index, (stamp, topic) in enumerate(
                            zip(times, topics, strict=True)
                        )
                    ]
                )
            if plan.music_status == "waiting_for_tracks":
                chosen = self.sampler.tracks(
                    candidates,
                    policy.tracks,
                    as_utc(plan.starts_at)
                    - timedelta(days=policy.cooldown_windows),
                )
                if len(
                    chosen
                ) == policy.tracks and await self.plans.claim_music(plan.id):
                    times = self.sampler.times(
                        available_start, end, policy.tracks
                    )
                    await self.jobs.create_many(
                        [
                            self._slot(
                                plan,
                                access.owner_id,
                                "music",
                                index + 1,
                                stamp,
                                end,
                                policy.grace_seconds,
                                track_id=track,
                            )
                            for index, (stamp, track) in enumerate(
                                zip(times, chosen, strict=True)
                            )
                        ]
                    )
                elif len(
                    chosen
                ) < policy.tracks and await self.plans.claim_warning(plan.id):
                    await self.jobs.create(
                        PublicationJobModel(
                            plan_id=plan.id,
                            kind="reply",
                            owner_id=access.owner_id,
                            channel_id=access.owner_id,
                            automatic=False,
                            text="برای برنامهٔ موسیقی امشب حداقل سه آهنگ ف"
                            "عال لازم دارم 🎧",
                            scheduled_at=now,
                            next_attempt_at=now,
                        )
                    )
            existing = await self.reader.jobs(plan.id)
            active_ids = {c.track.id for c in candidates}
            invalid = [
                j
                for j in existing
                if j.kind == "music"
                and j.status in {"pending", "blocked"}
                and j.track_id not in active_ids
            ]
            excluded = {
                j.track_id
                for j in existing
                if j.kind == "music"
                and j.track_id in active_ids
                and j.track_id is not None
            }
            replacements = self.sampler.tracks(
                candidates,
                len(invalid),
                as_utc(plan.starts_at)
                - timedelta(days=policy.cooldown_windows),
                exclude=excluded,
            )
            await self.jobs.replace_many(
                [
                    TrackReplacement(
                        job_id=j.id,
                        track_id=replacements[i]
                        if i < len(replacements)
                        else None,
                    )
                    for i, j in enumerate(invalid)
                ]
            )
        row = await self.plans.for_evening(access.channel_id, day)
        if row is None:
            raise ValueError("Plan not found")
        return row

    def _slot(
        self,
        plan: PlanModel,
        owner: int,
        kind: PublicationKind,
        ordinal: int,
        stamp: datetime,
        end: datetime,
        grace: int,
        *,
        track_id: int | None = None,
        topic: str | None = None,
    ) -> PublicationJobModel:
        return PublicationJobModel(
            plan_id=plan.id,
            kind=kind,
            ordinal=ordinal,
            track_id=track_id,
            channel_id=plan.channel_id,
            owner_id=owner,
            scheduled_at=stamp,
            deadline_at=min(stamp + timedelta(seconds=grace), end),
            next_attempt_at=stamp,
            topic=topic,
        )
