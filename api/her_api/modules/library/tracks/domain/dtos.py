from datetime import datetime

from pydantic import BaseModel

from her_api.modules.library.tracks.domain.models import TrackModel
from her_contracts.media import Mood


class TrackChange(BaseModel):
    active: bool | None = None
    mood: Mood | None = None
    tags_json: str | None = None


class TrackCandidate(BaseModel):
    track: TrackModel
    last_played: datetime | None = None
