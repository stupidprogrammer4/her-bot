from datetime import datetime

from pydantic import BaseModel

from her_api.modules.publishing.deliveries.domain.models import (
    PublicationJobModel,
)


class JobChange(BaseModel):
    status: str | None = None
    text: str | None = None
    track_id: int | None = None
    next_attempt_at: datetime | None = None
    lease_expires_at: datetime | None = None
    sent_at: datetime | None = None
    message_id: int | None = None
    failure_reason: str | None = None
    retry_confirmation_expires_at: datetime | None = None


class TrackReplacement(BaseModel):
    job_id: int
    track_id: int | None


class UnnotifiedPublication(BaseModel):
    job: PublicationJobModel
