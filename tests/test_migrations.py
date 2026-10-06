import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from alembic import command
from alembic.config import Config
from dishka import make_async_container
from papilio.core.bootstrap import Bootstrapper
from papilio.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from her_api.config.providers import task_providers
from her_api.config.settings import HerSettings
from her_api.modules.ops.settings.interfaces import ISettingsService
from her_api.modules.persona.privacy.app.defaults import initial_persona
from her_contracts.policy import PersonaFact, PersonaPolicy


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upgrade_preserves_policy_and_accepts_large_persona(
    tmp_path, monkeypatch
):
    database = os.getenv("HER_TEST_DATABASE_URL")
    redis = os.getenv("HER_TEST_REDIS_URL")
    if not database or not redis:
        pytest.skip("Isolated MySQL and Redis required")
    if not database.rsplit("/", 1)[-1].startswith("her_test"):
        raise ValueError("An isolated test schema is required")
    root = Path(__file__).resolve().parents[1]
    raw = yaml.safe_load((root / "config.yml.sample").read_text())
    raw["db"]["dsn"] = database
    raw["tasks"]["url"] = redis
    raw["security"] = {
        "service_key": "migration-test-service-key" * 2,
        "identity_hashes": [],
    }
    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(raw))
    monkeypatch.setenv("PAPILIO_CONFIG", str(config_path))
    monkeypatch.setenv("HER_ENV_FILE", str(tmp_path / "absent.env"))
    monkeypatch.setenv("HER_DATABASE_URL", database)
    monkeypatch.setenv("HER_REDIS_URL", redis)
    monkeypatch.setenv("HER_SERVICE_KEY", raw["security"]["service_key"])
    monkeypatch.setenv("HER_IDENTITY_HASHES", "")
    get_settings.cache_clear()
    Bootstrapper(["her_api.modules"]).boot_sqlmodels()
    engine = create_async_engine(database, hide_parameters=True)
    configuration = Config(str(root / "api/alembic.ini"))
    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.drop_all)
            await connection.execute(
                text("DROP TABLE IF EXISTS alembic_version")
            )
        await asyncio.to_thread(
            command.upgrade, configuration, "20261006_initial"
        )
        previous = json.dumps(
            {
                "owner_id": 10001,
                "channel_id": -10020001,
                "paused": True,
                "group_enabled": False,
            }
        )
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO tbl_settings (`key`,value,revision) "
                    "VALUES ('access',:value,7)"
                ),
                {"value": previous},
            )
            await connection.execute(
                text(
                    "INSERT INTO tbl_tracks (bot_id,file_id,file_unique_id,"
                    "source_chat_id,source_message_id,title,performer,filename,"
                    "duration,mood,tags_json,active) VALUES "
                    "(90001,'FilePreserved','UniquePreserved',10001,1,"
                    "'','','',10,'neutral','[]',1)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO tbl_channel_imports "
                    "(token,owner_id,channel_id,payload,matching_channel,"
                    "status,expires_at) VALUES "
                    "('LegacyToken',10001,-10020001,'[]',1,'preview',:expires)"
                ),
                {"expires": datetime(2026, 10, 8)},
            )
        await asyncio.to_thread(command.upgrade, configuration, "head")
        async with engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT id,value,revision FROM tbl_settings "
                            "WHERE `key`='access'"
                        )
                    )
                )
                .mappings()
                .one()
            )
            assert row["id"] == 1 and row["revision"] == 7
            assert row["value"] == previous
            imported = (
                (
                    await connection.execute(
                        text(
                            "SELECT token,payload,preview_json,update_id "
                            "FROM tbl_channel_imports"
                        )
                    )
                )
                .mappings()
                .one()
            )
            assert dict(imported) == {
                "token": "LegacyToken",
                "payload": "[]",
                "preview_json": "",
                "update_id": None,
            }
        settings = HerSettings.model_validate(raw)
        container = make_async_container(*task_providers(settings))
        try:
            async with container() as scope:
                service = await scope.get(ISettingsService)
                persona = initial_persona().model_copy(
                    update={
                        "system_prompt": "x" * 16000,
                        "facts": [
                            PersonaFact(
                                key="fact-" + str(i), content="ح" * 500
                            )
                            for i in range(50)
                        ],
                    }
                )
                assert len(persona.model_dump_json().encode()) > 65535
                await service.bootstrap("persona", persona)
            async with container() as scope:
                service = await scope.get(ISettingsService)
                saved = await service.get("persona")
                assert isinstance(saved.value, PersonaPolicy)
                assert saved.value == persona
                from her_api.modules.library.tracks.interfaces import (
                    ITrackService,
                )

                tracks = await scope.get(ITrackService)
                preserved_track = await tracks.get(1)
                assert preserved_track.file_id == "FilePreserved"
                assert preserved_track.file_unique_id == "UniquePreserved"
            await asyncio.to_thread(command.upgrade, configuration, "head")
            async with container() as scope:
                service = await scope.get(ISettingsService)
                preserved = await service.get("access")
                assert preserved.revision == 7
        finally:
            await container.close()
    finally:
        await engine.dispose()
        get_settings.cache_clear()
