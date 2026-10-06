from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from her_api.modules.publishing.deliveries.interfaces import (
    IPublicationCommands,
)


class Deliver(RedisScheduler):
    def __init__(self, commands: IPublicationCommands):
        self.commands = commands

    async def run(self, job_id: int) -> None:
        try:
            await self.commands.deliver(job_id)
        except Exception as error:
            raise RuntimeError(
                "Her task failed: " + type(error).__name__
            ) from None
