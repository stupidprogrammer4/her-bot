from datetime import date

from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import CharField, IntField
from sqlmodel import Field


class DailyCallModel(PersistenceEntity):
    day: date = Field(unique=True)
    calls: int = IntField(default=0)


class ModelCallModel(PersistenceEntity):
    purpose: str = CharField(24)
    model: str = CharField(150)
    status: str = CharField(24, default="running")
    input_tokens: int = IntField(default=0)
    output_tokens: int = IntField(default=0)
    error_code: str | None = CharField(100, default=None, nullable=True)
