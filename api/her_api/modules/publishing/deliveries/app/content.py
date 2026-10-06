import re
from difflib import SequenceMatcher

from her_api.modules.ai.generation.domain.errors import ModelUnavailable
from her_api.modules.ai.generation.interfaces import IGenerationCommands
from her_api.modules.content.channel.interfaces import IChannelQueries
from her_api.modules.library.tracks.interfaces import ITrackService
from her_api.modules.persona.privacy.app.guard import IdentityGuard, normalize
from her_api.modules.publishing.deliveries.domain.models import (
    PublicationJobModel,
)
from her_api.modules.publishing.deliveries.infra.readers import (
    PublicationReader,
)
from her_api.shared.clock import Clock
from her_api.shared.dates import as_utc
from her_contracts.generation import GenerationRequest
from her_contracts.policy import SettingsSnapshot


class PublicationContent:
    def __init__(
        self,
        generation: IGenerationCommands,
        channel: IChannelQueries,
        tracks: ITrackService,
        reader: PublicationReader,
        guard: IdentityGuard,
        clock: Clock,
    ):
        self.clock = clock
        self.generation, self.channel, self.tracks, self.reader, self.guard = (
            generation,
            channel,
            tracks,
            reader,
            guard,
        )

    def valid(
        self, text: str, limit: int, recent: list[str], *, lines: int = 5
    ) -> bool:
        value = text.strip()
        normalized = normalize(value)
        return (
            bool(value)
            and len(value) <= limit
            and len(value.splitlines()) <= lines
            and not re.search(
                r"https?://|www\.|system\s*prompt|tool_calls|trusted_context|owner_private",
                normalized,
            )
            and not self.guard.contains(value)
            and not any(
                SequenceMatcher(None, normalized, normalize(old)).ratio()
                > 0.88
                for old in recent
            )
        )

    async def prepare(
        self, job: PublicationJobModel, settings: SettingsSnapshot
    ) -> str:
        if job.text is not None:
            return self.guard.require_safe(job.text)
        context = await self.channel.context()
        recent = await self.reader.recent_texts(job.channel_id)
        mode = (
            "channel_caption"
            if job.kind in {"music", "preview"}
            else "greeting"
            if job.kind == "greeting"
            else "channel_post"
        )
        limit = (
            500
            if mode == "channel_caption"
            else 400
            if mode == "greeting"
            else 700
        )
        data = {
            "topic": job.topic,
            "recent_public_posts": [
                p.model_dump(mode="json") for p in context.posts
            ],
            "instruction": "Write only the final Persian public text"
            ", no explanation or invented real events"
            ".",
        }
        if job.track_id is not None:
            track = await self.tracks.get(job.track_id)
            data["track"] = {
                "title": track.title,
                "performer": track.performer,
                "mood": track.mood,
            }
        remaining = (
            (as_utc(job.deadline_at) - self.clock.now()).total_seconds()
            if job.deadline_at
            else 25
        )
        try:
            reply = await self.generation.complete(
                GenerationRequest(
                    mode=mode,
                    data=data,
                    deadline_seconds=max(0.01, min(25, remaining)),
                )
            )
            text = (reply.message.content or "").strip()
            if self.valid(text, limit, recent):
                return text
        except (ValueError, ModelUnavailable):
            pass
        if mode == "channel_caption":
            return self.guard.require_safe(settings.persona.music_fallback)
        if mode == "greeting":
            return self.guard.require_safe(settings.persona.greeting_fallback)
        choices = settings.persona.fallbacks.get(job.topic or "", [])
        safe = [text for text in choices if self.valid(text, limit, recent)]
        if not safe:
            raise ValueError("No distinct safe text available")
        return safe[job.id % len(safe)]
