from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from her_api.config.security import service_auth
from her_api.modules.content.channel.interfaces import IChannelCommands
from her_api.modules.ops.settings.interfaces import ISettingsQueries


class ExportInput(BaseModel):
    raw: str = Field(max_length=10 * 1024 * 1024)
    actor_id: int = Field(gt=0)
    chat_id: int = Field(gt=0)
    update_id: int = Field(ge=0)
    message_id: int = Field(gt=0)


router = APIRouter(
    prefix="/internal/channel",
    route_class=DishkaRoute,
    dependencies=[Depends(service_auth)],
)


@router.get("/import/{actor_id}")
async def import_open(actor_id: int, commands: FromDishka[IChannelCommands]):
    opened = await commands.import_open(actor_id)
    return {"open": opened}


@router.post("/import")
async def preview(
    data: ExportInput,
    commands: FromDishka[IChannelCommands],
    queries: FromDishka[ISettingsQueries],
):
    settings = await queries.snapshot()
    if (
        data.chat_id != settings.access.owner_id
        or data.actor_id != settings.access.owner_id
    ):
        raise ValueError("Owner private chat required")
    result = await commands.import_preview(
        data.raw, data.actor_id, data.update_id, data.message_id
    )
    return result


@router.post("/heartbeat")
async def heartbeat(commands: FromDishka[IChannelCommands]):
    await commands.heartbeat()
    return {"status": "ok"}
