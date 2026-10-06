import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr


class BotSettings(BaseModel):
    token: SecretStr
    service_key: SecretStr = Field(min_length=32)
    backend_url: str = "http://api:8000"
    host: str = "0.0.0.0"
    port: int = 8080

    @classmethod
    def environment(cls) -> "BotSettings":
        load_dotenv(os.getenv("HER_ENV_FILE", ".env"))
        return cls(
            token=SecretStr(os.environ["HER_BOT_TOKEN"]),
            service_key=SecretStr(os.environ["HER_SERVICE_KEY"]),
            backend_url=os.getenv("HER_BACKEND_URL", "http://api:8000"),
            host=os.getenv("HER_GATEWAY_HOST", "0.0.0.0"),
            port=int(os.getenv("HER_GATEWAY_PORT", "8080")),
        )
