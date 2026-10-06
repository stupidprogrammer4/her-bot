from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter
from papilio.infra.db.uow import MySQLUnitOfWork
from papilio.infra.redis.client import RedisClient
from sqlalchemy import text

router = APIRouter(route_class=DishkaRoute)


@router.get("/health")
async def health(
    uow: FromDishka[MySQLUnitOfWork], redis: FromDishka[RedisClient]
):
    await uow.execute(text("SELECT 1"))
    await redis.ping()
    return {"status": "ok"}
