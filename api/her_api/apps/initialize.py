import asyncio
import os

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv

from her_api.apps.bootstrap import bootstrap


async def initialize() -> None:
    load_dotenv(os.getenv("HER_ENV_FILE", ".env"))
    configuration = Config("api/alembic.ini")
    await asyncio.to_thread(command.upgrade, configuration, "head")
    await bootstrap()


if __name__ == "__main__":
    asyncio.run(initialize())
