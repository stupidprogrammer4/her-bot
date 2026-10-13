import importlib.util
import json
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.asyncio


def apply_provider_migration(connection):
    path = Path("api/migrations/versions/20261013_groq_model.py")
    spec = importlib.util.spec_from_file_location("groq_upgrade", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(connection)):
        module.upgrade()


async def test_groq_upgrade_preserves_existing_policy_limits(native):
    engine = create_async_engine(native.settings.db.dsn)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE tbl_settings SET value=JSON_SET(value, "
                    "'$.model','legacy/free:free',"
                    "'$.reasoning_effort','none'), "
                    "revision=7 WHERE `key`='model'"
                )
            )
        async with engine.begin() as connection:
            prior = (
                await connection.execute(
                    text("SELECT value FROM tbl_settings WHERE `key`='model'")
                )
            ).scalar_one()
            await connection.run_sync(apply_provider_migration)
        async with engine.begin() as connection:
            value, revision = (
                await connection.execute(
                    text(
                        "SELECT value,revision FROM tbl_settings "
                        "WHERE `key`='model'"
                    )
                )
            ).one()
        old = json.loads(prior)
        migrated = json.loads(value)
        assert migrated.pop("model") == "qwen/qwen3.8-27b"
        assert migrated.pop("reasoning_effort") is None
        old.pop("model")
        old.pop("reasoning_effort")
        assert migrated == old
        assert revision == 8
    finally:
        await engine.dispose()
