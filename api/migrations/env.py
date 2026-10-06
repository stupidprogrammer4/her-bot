import asyncio
import os

from alembic import context
from dotenv import load_dotenv
from papilio.core.bootstrap import Bootstrapper
from papilio.core.config import get_settings
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from her_api.config.settings import HerSettings

load_dotenv(os.getenv("HER_ENV_FILE", ".env"))
settings = get_settings(HerSettings)
Bootstrapper(settings.app.modules).boot_sqlmodels()
if settings.db is None:
    raise RuntimeError("MySQL configuration required")
url = context.config.get_main_option("sqlalchemy.url") or settings.db.dsn


def run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=SQLModel.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def online() -> None:
    engine = create_async_engine(
        url, poolclass=pool.NullPool, hide_parameters=True
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=url,
        target_metadata=SQLModel.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif (connection := context.config.attributes.get("connection")) is not None:
    run(connection)
else:
    asyncio.run(online())
