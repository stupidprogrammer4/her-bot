from collections.abc import Awaitable
from typing import Protocol

from her_api.modules.library.tracks.domain.dtos import TrackChange
from her_api.modules.library.tracks.domain.models import TrackModel
from her_contracts.media import AudioUpload, TrackPage


class ITrackService(Protocol):
    def get(self, id: int) -> Awaitable[TrackModel]: ...
    def upload(self, data: AudioUpload) -> Awaitable[TrackModel]: ...
    def change(self, id: int, data: TrackChange) -> Awaitable[None]: ...
    def page(
        self, page: int, per_page: int = 10, mood: str | None = None
    ) -> Awaitable[TrackPage]: ...
