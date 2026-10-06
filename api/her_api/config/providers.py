from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, alias, provide
from papilio.core.bootstrap import Bootstrapper
from papilio.core.config import RedisConfig, Settings
from papilio.providers.base import CoreProvider
from papilio.providers.db import MySQLProvider
from papilio.providers.redis import RedisProvider

from her_api.config.settings import HerSettings
from her_api.shared.clock import Clock, SystemClock


class RuntimeProvider(Provider):
    settings = alias(Settings, provides=HerSettings)

    @provide(scope=Scope.APP)
    async def http(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=5), trust_env=False
        ) as client:
            yield client

    clock = provide(SystemClock, provides=Clock, scope=Scope.APP)


def infrastructure_providers(settings: HerSettings):
    if settings.db is None:
        raise ValueError("MySQL configuration required")
    return [
        MySQLProvider(settings.db),
        RedisProvider(
            RedisConfig(
                url=settings.tasks.url,
                max_connections=10,
                socket_timeout=10,
                socket_connect_timeout=5,
                health_check_interval=30,
            )
        ),
        RuntimeProvider(),
    ]


def task_providers(settings: HerSettings):
    return [
        CoreProvider(settings),
        *infrastructure_providers(settings),
        *Bootstrapper(settings.app.modules).boot_providers(),
    ]
