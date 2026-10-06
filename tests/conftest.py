import asyncio
import hashlib
import os
import socket
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
import uvicorn
import yaml
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiohttp import web
from alembic import command
from alembic.config import Config
from dishka import Provider, Scope, provide
from fastapi.exceptions import RequestValidationError
from papilio.api.application import create_app
from papilio.core.bootstrap import Bootstrapper
from papilio.core.config import get_settings
from papilio.errors.exceptions import NotFoundException
from papilio.infra.db.transaction import transaction
from papilio.infra.db.uow import MySQLUnitOfWork
from papilio_tasks.apps.lifecycle import Producers
from papilio_tasks.apps.schedulers.redis import create_app as scheduler_app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from taskiq import AsyncTaskiqTask

from her_api.config.errors import (
    internal_failure,
    invalid_operation,
    invalid_request,
    missing_record,
)
from her_api.config.providers import infrastructure_providers, task_providers
from her_api.config.settings import HerSettings
from her_api.modules.ops.inbox.tasks.schedulers.process import ProcessUpdate
from her_api.modules.ops.settings.interfaces import ISettingsService
from her_api.modules.persona.privacy.app.defaults import initial_persona
from her_api.shared.clock import Clock
from her_bot.app.delivery import Delivery
from her_bot.app.gateway import Gateway
from her_bot.config.settings import BotSettings
from her_bot.infra.backend import Backend
from her_contracts.policy import AccessPolicy, ModelPolicy, WindowPolicy
from her_contracts.telegram import IncomingMessage

OWNER = 10001
CHANNEL = -10020001
GROUP = -10030001
BOT_ID = 90001
TEST_TOKEN = "90001:" + "a" * 35
ROOT = Path(__file__).resolve().parents[1]


@dataclass
class ControlledServices:
    model_status: int = 200
    model_replies: list[dict[str, Any]] = field(default_factory=list)
    model_requests: list[dict[str, Any]] = field(default_factory=list)
    telegram_replies: list[dict[str, Any]] = field(default_factory=list)
    telegram_errors: dict[str, dict[str, Any]] = field(default_factory=dict)
    telegram_requests: list[dict[str, Any]] = field(default_factory=list)
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    next_message_id: int = 4000

    async def model(self, request: web.Request) -> web.Response:
        body = await request.json()
        self.model_requests.append(body)
        if self.model_status != 200:
            return web.json_response(
                {"error": {"code": self.model_status}},
                status=self.model_status,
            )
        message = (
            self.model_replies.pop(0)
            if self.model_replies
            else {
                "role": "assistant",
                "content": "من یه شخصیت مجازی‌ام؛ می‌تونیم آروم حرف بزنیم 🎀",
            }
        )
        return web.json_response(
            {
                "choices": [{"message": message}],
                "usage": {"prompt_tokens": 15, "completion_tokens": 20},
            }
        )

    async def telegram(self, request: web.Request) -> web.Response:
        body = dict(await request.post())
        method = request.match_info["method"]
        body["method"] = method
        async with self.condition:
            self.telegram_requests.append(body)
            self.condition.notify_all()
        if body.get("text") in self.telegram_errors:
            reply = self.telegram_errors.pop(body["text"])
            status = reply.pop("http_status", 200)
            return web.json_response(reply, status=status)
        if self.telegram_replies:
            reply = self.telegram_replies.pop(0)
            status = reply.pop("http_status", 200)
            return web.json_response(reply, status=status)
        self.next_message_id += 1
        if method in {"deleteMessage", "answerCallbackQuery"}:
            result: Any = True
        elif method == "getUpdates":
            result = []
        else:
            chat_id = int(body.get("chat_id", str(OWNER)))
            result = {
                "message_id": int(
                    body.get("message_id", self.next_message_id)
                ),
                "date": int(datetime.now(UTC).timestamp()),
                "chat": {
                    "id": chat_id,
                    "type": "private" if chat_id > 0 else "channel",
                },
                "from": {"id": BOT_ID, "is_bot": True, "first_name": "Her"},
                "text": body.get("text", ""),
                "caption": body.get("caption"),
            }
        return web.json_response({"ok": True, "result": result})

    async def received(
        self, predicate: Callable[[dict[str, Any]], bool], timeout: float = 15
    ) -> dict[str, Any]:
        async with asyncio.timeout(timeout), self.condition:
            await self.condition.wait_for(
                lambda: any(predicate(r) for r in self.telegram_requests)
            )
        return next(r for r in self.telegram_requests if predicate(r))


class FixedClock:
    def __init__(self):
        self.instant: datetime | None = None

    def now(self) -> datetime:
        return self.instant or datetime.now(UTC)


class ClockProvider(Provider):
    def __init__(self, clock: FixedClock):
        super().__init__()
        self.clock = clock

    @provide(scope=Scope.APP, override=True)
    def provide_clock(self) -> Clock:
        return self.clock


@asynccontextmanager
async def serve(app: web.Application) -> AsyncIterator[str]:
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.setblocking(False)
    await web.SockSite(runner, sock).start()
    try:
        yield "http://127.0.0.1:" + str(sock.getsockname()[1])
    finally:
        await runner.cleanup()


@dataclass
class Harness:
    app: Any
    tasks: Any
    http: httpx.AsyncClient
    services: ControlledServices
    settings: HerSettings
    clock: FixedClock
    worker: asyncio.subprocess.Process
    worker_log: Path
    bot: Bot
    backend: Backend

    def scope(self):
        return self.app.state.dishka_container()

    async def post(self, data: IncomingMessage) -> dict[str, Any]:
        response = await self.http.post(
            "/internal/updates", json=data.model_dump(mode="json")
        )
        assert response.status_code == 200, response.text
        result = response.json()
        if result.get("task_id"):
            task = AsyncTaskiqTask(
                result["task_id"], self.tasks.broker.result_backend
            )
            completed = await task.wait_result(timeout=15)
            assert not completed.is_err, self.worker_log.read_text()[-5000:]
        return result

    async def rows(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        async with self.scope() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            result = await uow.execute(text(query), params or {})
            return [dict(r) for r in result.mappings()]

    async def execute(
        self, query: str, params: dict[str, Any] | None = None
    ) -> None:
        async with self.scope() as scope:
            uow = await scope.get(MySQLUnitOfWork)
            async with transaction():
                await uow.execute(text(query), params or {})


@pytest_asyncio.fixture
async def native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Harness]:
    database = os.getenv("HER_TEST_DATABASE_URL")
    redis = os.getenv("HER_TEST_REDIS_URL")
    if not database or not redis:
        pytest.skip(
            "Set isolated HER_TEST_DATABASE_URL and HER_TEST_REDIS_URL"
        )
    if not database.rsplit("/", 1)[-1].startswith("her_test"):
        raise ValueError("An isolated her_test database is required")
    identifier = uuid4().hex
    key = uuid4().hex + uuid4().hex
    guard_hash = hashlib.sha256("نامفرضی".encode()).hexdigest()
    for name, value in {
        "HER_DATABASE_URL": database,
        "HER_REDIS_URL": redis,
        "HER_SERVICE_KEY": key,
        "OPENROUTER_API_KEY": "test-key",
        "HER_IDENTITY_HASHES": guard_hash,
        "HER_ENV_FILE": str(tmp_path / "absent.env"),
    }.items():
        monkeypatch.setenv(name, value)
    services = ControlledServices()
    external = web.Application()
    external.router.add_post("/model", services.model)
    external.router.add_post(
        "/bot" + TEST_TOKEN + "/{method}", services.telegram
    )
    async with serve(external) as external_url:
        raw = yaml.safe_load((ROOT / "config.yml.sample").read_text())
        raw["security"] = {"service_key": key, "identity_hashes": [guard_hash]}
        raw["db"]["dsn"] = database
        raw["tasks"].update(
            url=redis,
            queue_name="her-test:" + identifier,
            consumer_group="her-test-workers:" + identifier,
            schedule_prefix="her-test-schedules:" + identifier,
            result_prefix="her-test-results:" + identifier,
        )
        raw["ai"] = {
            "api_key": "test-key",
            "endpoint": external_url + "/model",
        }
        config_path = tmp_path / "config.yml"
        monkeypatch.setenv("PAPILIO_CONFIG", str(config_path))
        engine = create_async_engine(database, hide_parameters=True)
        Bootstrapper(["her_api.modules"]).boot_sqlmodels()
        try:
            async with engine.begin() as connection:
                await connection.run_sync(SQLModel.metadata.drop_all)
                await connection.execute(
                    text("DROP TABLE IF EXISTS alembic_version")
                )
            config_path.write_text(yaml.safe_dump(raw))
            get_settings.cache_clear()
            alembic = Config(str(ROOT / "api/alembic.ini"))
            await asyncio.to_thread(command.upgrade, alembic, "head")
        finally:
            await engine.dispose()
        bot_settings = BotSettings(token=TEST_TOKEN, service_key=key)
        clock = FixedClock()
        settings = HerSettings.model_validate(raw)
        tasks = scheduler_app(
            settings.tasks,
            providers=task_providers(settings),
            modules=settings.app.modules,
        )
        app = create_app(
            settings,
            providers=[
                *infrastructure_providers(settings),
                ClockProvider(clock),
            ],
            middleware=[],
            lifespan=Producers(tasks),
            exception_handlers={
                ValueError: invalid_operation,
                NotFoundException: missing_record,
                RequestValidationError: invalid_request,
                Exception: internal_failure,
            },
            docs_url=None,
        )
        api_socket = socket.socket()
        api_socket.bind(("127.0.0.1", 0))
        api_socket.setblocking(False)
        api_url = "http://127.0.0.1:" + str(api_socket.getsockname()[1])
        bot_settings.backend_url = api_url
        async with httpx.AsyncClient(timeout=10) as backend_http:
            backend = Backend(backend_http, bot_settings)
            bot = Bot(
                TEST_TOKEN,
                session=AiohttpSession(
                    api=TelegramAPIServer.from_base(external_url)
                ),
            )
            gateway = Gateway(Delivery(bot, backend), bot_settings)
            gateway.ready = True
            async with serve(gateway.app) as gateway_url:
                raw["telegram"]["gateway_url"] = gateway_url
                settings.telegram.gateway_url = gateway_url
                config_path.write_text(yaml.safe_dump(raw))
                get_settings.cache_clear()
                async with app.state.dishka_container() as scope:
                    service = await scope.get(ISettingsService)
                    await service.bootstrap(
                        "access",
                        AccessPolicy(
                            owner_id=OWNER, channel_id=CHANNEL, group_id=GROUP
                        ),
                    )
                    await service.bootstrap(
                        "model", ModelPolicy(model="test-model")
                    )
                    await service.bootstrap(
                        "window", WindowPolicy(text_min=0, text_max=0)
                    )
                    await service.bootstrap("persona", initial_persona())
                server = uvicorn.Server(
                    uvicorn.Config(
                        app,
                        log_level="critical",
                        access_log=False,
                        lifespan="on",
                    )
                )
                api_task = asyncio.create_task(
                    server.serve(sockets=[api_socket])
                )
                await tasks.connect()
                worker_log = tmp_path / "worker.log"
                log = worker_log.open("wb")
                env = os.environ | {
                    "PYTHONPATH": str(ROOT / "api")
                    + ":"
                    + str(ROOT / "packages/contracts")
                }
                worker = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "taskiq",
                    "worker",
                    "her_api.apps.scheduler:broker",
                    "--workers",
                    "1",
                    "--max-async-tasks",
                    "8",
                    "--log-level",
                    "WARNING",
                    env=env,
                    cwd=ROOT,
                    stdout=log,
                    stderr=log,
                )
                scheduler = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "taskiq",
                    "scheduler",
                    "her_api.apps.scheduler:scheduler",
                    "--log-level",
                    "WARNING",
                    env=env,
                    cwd=ROOT,
                    stdout=log,
                    stderr=log,
                )
                async with httpx.AsyncClient(
                    base_url=api_url,
                    headers={"Authorization": "Bearer " + key},
                    timeout=10,
                ) as client:
                    try:
                        # Confirm real worker startup and queue consumption.
                        ready = await ProcessUpdate.enqueue(0)
                        completed = await ready.wait_result(timeout=15)
                        assert not completed.is_err, worker_log.read_text()
                        yield Harness(
                            app,
                            tasks,
                            client,
                            services,
                            settings,
                            clock,
                            worker,
                            worker_log,
                            bot,
                            backend,
                        )
                    finally:
                        worker.terminate()
                        scheduler.terminate()
                        await asyncio.gather(worker.wait(), scheduler.wait())
                        log.close()
                        server.should_exit = True
                        await api_task
                        await bot.session.close()
                        await tasks.stop()
                        get_settings.cache_clear()
