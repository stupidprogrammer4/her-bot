import json

from pydantic import TypeAdapter

from her_api.modules.library.tracks.domain.dtos import TrackChange
from her_api.modules.library.tracks.interfaces import ITrackService
from her_api.modules.publishing.deliveries.interfaces import (
    IPublicationCommands,
)
from her_contracts.commands import CommandResult
from her_contracts.media import Mood
from her_contracts.publications import ManualPublication
from her_contracts.telegram import IncomingMessage


class ArchiveCommands:
    def __init__(
        self, tracks: ITrackService, publications: IPublicationCommands
    ):
        self.tracks, self.publications = tracks, publications

    async def handle(
        self, data: IncomingMessage, command: str, args: str
    ) -> CommandResult | None:
        if command not in {"tracks", "tag", "disable", "enable", "preview"}:
            return None
        if data.chat_type != "private":
            return CommandResult(text="این بخش فقط تو گفت‌وگوی خصوصی فعاله 🎧")
        if command == "tracks":
            page = int(args or "1")
            result = await self.tracks.page(page)
            lines = [
                "🎧 آرشیو · صفحهٔ "
                + str(page)
                + " · "
                + str(result.total)
                + " آهنگ"
            ]
            lines.extend(
                str(t.id)
                + " · "
                + (t.title or t.filename or "بدون عنوان")
                + (" — " + t.performer if t.performer else "")
                + " · "
                + t.mood
                + (" ⏸" if not t.active else "")
                for t in result.items
            )
            if page * 10 < result.total:
                lines.append("صفحهٔ بعد: /tracks " + str(page + 1))
            return CommandResult(text="\n\n".join(lines))
        parts = args.split(maxsplit=2)
        track_id = int(parts[0])
        if command == "preview":
            job = await self.publications.reserve(
                ManualPublication(
                    update_id=data.update_id,
                    actor_id=data.sender_id or 0,
                    kind="preview",
                    destination="owner",
                    track_id=track_id,
                )
            )
            return CommandResult(
                text="پیش‌نمایش در صفه 🎧\nکار: " + str(job.id)
            )
        if command == "tag":
            mood = TypeAdapter(Mood).validate_python(parts[1])
            tags = (
                [t.strip() for t in parts[2].split(",") if t.strip()]
                if len(parts) > 2
                else []
            )
            await self.tracks.change(
                track_id,
                TrackChange(
                    mood=mood, tags_json=json.dumps(tags, ensure_ascii=False)
                ),
            )
        else:
            await self.tracks.change(
                track_id, TrackChange(active=command == "enable")
            )
        return CommandResult(text="آرشیو به‌روز شد 🎧")
