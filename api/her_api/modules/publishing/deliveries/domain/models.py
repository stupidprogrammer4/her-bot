from datetime import datetime

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    BoolField,
    CharField,
    ForeignKeyField,
    IntField,
    TextField,
    TimestampField,
)

from her_contracts.publications import PublicationKind


class PublicationJobModel(PersistenceEntity):
    plan_id: int | None = ForeignKeyField(
        "tbl_plans.id", nullable=True, default=None
    )
    kind: PublicationKind = CharField(16)
    ordinal: int = IntField(default=1)
    track_id: int | None = ForeignKeyField(
        "tbl_tracks.id", nullable=True, default=None
    )
    channel_id: int = BigIntField()
    owner_id: int = BigIntField()
    automatic: bool = BoolField(default=True)
    update_id: int | None = BigIntField(nullable=True, default=None)
    write_slot: int | None = IntField(nullable=True, default=None)
    topic: str | None = CharField(120, nullable=True, default=None)
    text: str | None = TextField(nullable=True, default=None)
    scheduled_at: datetime = TimestampField()
    deadline_at: datetime | None = TimestampField(nullable=True, default=None)
    next_attempt_at: datetime = TimestampField()
    status: str = CharField(24, default="pending", index=True)
    attempts: int = IntField(default=0)
    preparing_started_at: datetime | None = TimestampField(
        nullable=True, default=None
    )
    send_started_at: datetime | None = TimestampField(
        nullable=True, default=None
    )
    sent_at: datetime | None = TimestampField(nullable=True, default=None)
    message_id: int | None = BigIntField(nullable=True, default=None)
    target_message_id: int | None = IntField(nullable=True, default=None)
    parent_job_id: int | None = ForeignKeyField(
        "tbl_publication_jobs.id", nullable=True, unique=True, default=None
    )
    lease_expires_at: datetime | None = TimestampField(
        nullable=True, default=None
    )
    failure_reason: str | None = CharField(120, nullable=True, default=None)
    retry_confirmation_expires_at: datetime | None = TimestampField(
        nullable=True, default=None
    )


class DeliveryGateModel(PersistenceEntity):
    channel_id: int = BigIntField(unique=True)
    job_id: int | None = BigIntField(nullable=True, default=None)
    expires_at: datetime | None = TimestampField(nullable=True, default=None)
