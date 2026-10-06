from datetime import datetime

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import (
    BigIntField,
    CharField,
    TextField,
    TimestampField,
)


class InboxModel(PersistenceEntity):
    update_id: int = BigIntField(unique=True)
    payload: str = TextField()
    status: str = CharField(20, default="pending", index=True)
    lease_expires_at: datetime | None = TimestampField(
        nullable=True, default=None
    )
    error_code: str | None = CharField(60, nullable=True, default=None)
