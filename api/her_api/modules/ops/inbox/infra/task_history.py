from datetime import datetime

from papilio.infra.redis.client import RedisClient, resolve

from her_api.config.settings import HerSettings


class TaskHistoryStore:
    def __init__(self, redis: RedisClient, settings: HerSettings):
        self.redis = redis
        self.stream = settings.tasks.queue_name

    async def prune(self, before: datetime) -> int:
        removed = await resolve(
            self.redis.client.execute_command(
                "XTRIM",
                self.stream,
                "MINID",
                "=",
                f"{int(before.timestamp() * 1000)}-0",
                "ACKED",
            )
        )
        if not isinstance(removed, int):
            raise RuntimeError("Redis did not return a stream trim count")
        return removed
