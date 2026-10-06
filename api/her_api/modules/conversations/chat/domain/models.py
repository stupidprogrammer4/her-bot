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
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlmodel import Field


class ConversationModel(PersistenceEntity):
    chat_id: int = BigIntField()
    user_id: int = BigIntField()
    active_request_id: int | None = BigIntField(nullable=True, default=None)
    lease_expires_at: datetime | None = TimestampField(
        nullable=True, default=None
    )


class ChatRequestModel(PersistenceEntity):
    update_id: int = BigIntField(unique=True)
    chat_id: int = BigIntField()
    user_id: int = BigIntField()
    message_id: int = IntField()
    private_owner: bool = BoolField()
    authenticated_owner: bool = BoolField()
    text: str = TextField()
    messages: str = Field(default="[]", sa_type=LONGTEXT)
    capabilities: str = TextField(default="[]")
    phase: str = CharField(16, default="initial")
    status: str = CharField(16, default="pending", index=True)
    round: int = IntField(default=0)
    tool_cursor: int = IntField(default=0)
    started_at: datetime | None = TimestampField(nullable=True, default=None)
    next_attempt_at: datetime = TimestampField()
    lease_expires_at: datetime | None = TimestampField(
        nullable=True, default=None
    )


class ConversationPairModel(PersistenceEntity):
    request_id: int = BigIntField(unique=True)
    chat_id: int = BigIntField()
    user_id: int = BigIntField()
    user_text: str = TextField()
    assistant_text: str = TextField()
