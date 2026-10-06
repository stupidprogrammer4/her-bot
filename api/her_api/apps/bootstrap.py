import asyncio
import os
from datetime import time

from dishka import make_async_container
from dotenv import load_dotenv
from papilio.core.config import get_settings

from her_api.config.providers import task_providers
from her_api.config.settings import HerSettings
from her_api.modules.ops.settings.interfaces import ISettingsService
from her_api.modules.persona.privacy.app.defaults import initial_persona
from her_contracts.policy import AccessPolicy, ModelPolicy, WindowPolicy


async def bootstrap() -> None:
    load_dotenv(os.getenv("HER_ENV_FILE", ".env"))
    settings = get_settings(HerSettings)
    container = make_async_container(*task_providers(settings))
    try:
        async with container() as scope:
            service = await scope.get(ISettingsService)
            owner = int(os.environ["HER_OWNER_TELEGRAM_ID"])
            channel = int(os.environ["HER_CHANNEL_ID"])
            group = os.getenv("HER_DISCUSSION_GROUP_ID")
            await service.bootstrap(
                "access",
                AccessPolicy(
                    owner_id=owner,
                    channel_id=channel,
                    group_id=int(group) if group else None,
                ),
            )
            await service.bootstrap("window", WindowPolicy(text_start=time(9)))
            await service.bootstrap(
                "model", ModelPolicy(model=os.environ["HER_OPENROUTER_MODEL"])
            )
            await service.bootstrap("persona", initial_persona())
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(bootstrap())
