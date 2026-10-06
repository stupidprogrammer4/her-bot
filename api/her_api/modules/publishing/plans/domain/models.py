from datetime import date, datetime

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    BoolField,
    CharField,
    IntField,
    TimestampField,
)
from sqlmodel import Field


class PlanModel(PersistenceEntity):
    channel_id: int = BigIntField()
    evening_date: date = Field()
    starts_at: datetime = TimestampField()
    ends_at: datetime = TimestampField()
    music_status: str = CharField(24, default="waiting_for_tracks")
    text_count: int | None = IntField(nullable=True, default=None)
    text_min_snapshot: int = IntField()
    text_max_snapshot: int = IntField()
    text_created_at: datetime | None = TimestampField(
        nullable=True, default=None
    )
    bootstrap_partial: bool = BoolField(default=False)
    warned_missing_tracks: bool = BoolField(default=False)
