import json

from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.tools.decorators import transactional

from her_api.modules.library.tracks.domain.dtos import TrackChange
from her_api.modules.library.tracks.domain.models import TrackModel
from her_api.modules.library.tracks.infra.mysql import TrackRepository
from her_api.modules.persona.privacy.app.guard import IdentityGuard
from her_contracts.media import AudioUpload, TrackOut, TrackPage


class TrackService:
    def __init__(self, repo: TrackRepository, guard: IdentityGuard):
        self.repo = repo
        self.guard = guard

    async def get(self, id: int) -> TrackModel:
        row = await self.repo.get(id)
        if row is None:
            raise NotFoundException(
                "Track not found", "record_not_found", "track", "id", id
            )
        return row

    @transactional
    async def upload(self, data: AudioUpload) -> TrackModel:
        clean = data.model_copy(
            update={
                "title": self.guard.scrub(data.title),
                "performer": self.guard.scrub(data.performer),
                "filename": self.guard.scrub(data.filename),
                "tags": [self.guard.scrub(t) for t in data.tags],
            }
        )
        row = await self.repo.upload(
            clean, json.dumps(clean.tags, ensure_ascii=False)
        )
        return row

    @transactional
    async def change(self, id: int, data: TrackChange) -> None:
        await self.get(id)
        if data.tags_json is not None:
            self.guard.require_safe(data.tags_json)
            tags = json.loads(data.tags_json)
            if (
                not isinstance(tags, list)
                or len(tags) > 20
                or any(
                    not isinstance(tag, str) or len(tag) > 60 for tag in tags
                )
            ):
                raise ValueError("Invalid track tags")
        await self.repo.change(id, data)

    async def page(
        self, page: int, per_page: int = 10, mood: str | None = None
    ) -> TrackPage:
        if page < 1 or not 1 <= per_page <= 30:
            raise ValueError("Invalid pagination")
        rows, count = await self.repo.page(page, per_page, mood)
        items = [
            TrackOut(
                **r.model_dump(exclude={"tags_json"}),
                tags=json.loads(r.tags_json),
            )
            for r in rows
        ]
        return TrackPage(items=items, page=page, total=count)
