from datetime import datetime

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    BoolField,
    CharField,
    IntField,
    TextField,
    TimestampField,
)
from sqlalchemy import Column, String
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlmodel import Field


class ChannelPostModel(PersistenceEntity):
    channel_id: int = BigIntField()
    message_id: int = IntField()
    text: str = TextField(default="")
    caption: str = TextField(default="")
    posted_at: datetime = TimestampField()
    edited_at: datetime | None = TimestampField(nullable=True, default=None)
    media_kind: str = CharField(20, default="text")
    origin: str = CharField(40, default="live")
    active: bool = BoolField(default=True)


class ChannelImportModel(PersistenceEntity):
    token: str = Field(
        sa_column=Column(
            String(64, collation="utf8mb4_bin"), unique=True, nullable=False
        ),
    )
    owner_id: int = BigIntField()
    update_id: int | None = BigIntField(
        nullable=True, unique=True, default=None
    )
    preview_json: str = TextField(default="")
    channel_id: int = BigIntField()
    payload: str = Field(sa_type=LONGTEXT, nullable=False)
    matching_channel: bool = BoolField()
    status: str = CharField(20, default="preview")
    expires_at: datetime = TimestampField()


class ImportSessionModel(PersistenceEntity):
    owner_id: int = BigIntField(unique=True)
    expires_at: datetime = TimestampField()


class ChannelCoverageModel(PersistenceEntity):
    channel_id: int = BigIntField(unique=True)
    last_update_received_at: datetime | None = TimestampField(
        nullable=True, default=None
    )
    last_heartbeat_at: datetime | None = TimestampField(
        nullable=True, default=None
    )
    gaps_json: str = TextField(default="[]")
