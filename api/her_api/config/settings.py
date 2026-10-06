import os
from typing import Any, Self

from papilio.core.config import Settings
from papilio_tasks.apps.taskiq import RedisSettings
from pydantic import BaseModel, Field, SecretStr, model_validator


class SecuritySettings(BaseModel):
    service_key: SecretStr = Field(min_length=32)
    identity_hashes: list[str] = Field(default_factory=list)


class ModelCredentials(BaseModel):
    api_key: SecretStr = SecretStr("")
    endpoint: str = "https://openrouter.ai/api/v1/chat/completions"


class TelegramTransport(BaseModel):
    gateway_url: str = "http://bots:8080"


class HerSettings(Settings):
    security: SecuritySettings
    ai: ModelCredentials = Field(default_factory=ModelCredentials)
    telegram: TelegramTransport = Field(default_factory=TelegramTransport)
    tasks: RedisSettings

    @model_validator(mode="before")
    @classmethod
    def environment(cls, raw: Any) -> Any:
        data = dict(raw)
        security = dict(data.get("security", {}))
        if key := os.getenv("HER_SERVICE_KEY"):
            security["service_key"] = key
        if hashes := os.getenv("HER_IDENTITY_HASHES"):
            security["identity_hashes"] = [
                s.strip() for s in hashes.split(",")
            ]
        data["security"] = security
        database = dict(data.get("db", {}))
        if url := os.getenv("HER_DATABASE_URL"):
            database["dsn"] = url
        data["db"] = database
        tasks = dict(data.get("tasks", {}))
        if url := os.getenv("HER_REDIS_URL"):
            tasks["url"] = url
        data["tasks"] = tasks
        ai = dict(data.get("ai", {}))
        if key := os.getenv("OPENROUTER_API_KEY"):
            ai["api_key"] = key
        data["ai"] = ai
        return data

    @model_validator(mode="after")
    def valid_database(self) -> Self:
        if self.db is None or not self.db.dsn.startswith("mysql+aiomysql://"):
            raise ValueError("Configure MySQL with aiomysql")
        return self
