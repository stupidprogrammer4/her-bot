from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends

from her_api.config.security import service_auth
from her_api.modules.ops.inbox.interfaces import IInboxCommands
from her_api.modules.ops.inbox.tasks.schedulers.process import ProcessUpdate
from her_api.modules.ops.settings.domain.dtos import SettingKey
from her_api.modules.ops.settings.interfaces import (
    ISettingsQueries,
    ISettingsService,
)
from her_contracts.policy import SettingWrite
from her_contracts.telegram import Admission, BotConfiguration, IncomingMessage

router = APIRouter(
    prefix="/internal",
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth)],
)


@router.post("/updates", response_model=Admission)
async def receive(
    data: IncomingMessage, commands: FromDishka[IInboxCommands]
) -> Admission:
    """Persist an authenticated Telegram update before acknowledging it."""
    result = await commands.admit(data)
    if result.accepted:
        try:
            task = await ProcessUpdate.enqueue(data.update_id)
            result.task_id = task.task_id
        except (ConnectionError, TimeoutError):
            pass
    return result


@router.get("/configuration", response_model=BotConfiguration)
async def configuration(
    queries: FromDishka[ISettingsQueries],
) -> BotConfiguration:
    settings = await queries.snapshot()
    return BotConfiguration(
        owner_id=settings.access.owner_id,
        channel_id=settings.access.channel_id,
        group_id=settings.access.group_id,
        display_name=settings.persona.display_name,
        aliases=settings.persona.aliases,
    )


@router.get("/settings/{key}")
async def setting(key: SettingKey, service: FromDishka[ISettingsService]):
    result = await service.get(key)
    return result


@router.put("/settings/{key}")
async def update_setting(
    key: SettingKey, data: SettingWrite, service: FromDishka[ISettingsService]
):
    result = await service.write(key, data.value, data.revision)
    return result
