from datetime import datetime

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    CharField,
    IntField,
    TextField,
    TimestampField,
)
from sqlalchemy import Column, String
from sqlmodel import Field


class OwnerActionModel(PersistenceEntity):
    update_id: int = BigIntField(unique=True)
    owner_id: int = BigIntField()
    write_slot: int = IntField(default=1)
    capability: str = CharField(40)
    result: str = TextField(default="")
    status: str = CharField(20, default="reserved")


class DeleteConfirmationModel(PersistenceEntity):
    token: str = Field(
        sa_column=Column(
            String(64, collation="utf8mb4_bin"), unique=True, nullable=False
        ),
    )
    owner_id: int = BigIntField()
    message_id: int = IntField()
    channel_id: int = BigIntField()
    expires_at: datetime = TimestampField()
    status: str = CharField(20, default="pending")
