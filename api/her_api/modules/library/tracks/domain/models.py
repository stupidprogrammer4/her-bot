from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    BoolField,
    CharField,
    IntField,
    TextField,
)
from sqlalchemy import Column, String
from sqlmodel import Field


class TrackModel(PersistenceEntity):
    bot_id: int = BigIntField()
    file_id: str = Field(
        sa_column=Column(String(512, collation="utf8mb4_bin"), nullable=False)
    )
    file_unique_id: str = Field(
        sa_column=Column(
            String(128, collation="utf8mb4_bin"), nullable=False, unique=True
        ),
    )
    source_chat_id: int = BigIntField()
    source_message_id: int = IntField()
    title: str = CharField(300, default="")
    performer: str = CharField(300, default="")
    filename: str = CharField(300, default="")
    duration: int = IntField(default=0)
    file_size: int | None = BigIntField(nullable=True, default=None)
    mood: str = CharField(16, default="neutral")
    tags_json: str = TextField(default="[]")
    active: bool = BoolField(default=True)
