from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PlanChange(BaseModel):
    music_status: Literal["waiting_for_tracks", "planned"] | None = None
    text_count: int | None = None
    text_created_at: datetime | None = None
    bootstrap_partial: bool | None = None
    warned_missing_tracks: bool | None = None
