from papilio.infra.db.schema.entity import PersistenceEntity
from papilio.infra.db.schema.fields import CharField, IntField
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlmodel import Field


class SettingModel(PersistenceEntity):
    key: str = CharField(32, unique=True)
    value: str = Field(sa_type=LONGTEXT, nullable=False)
    revision: int = IntField(default=1)
