from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from her_api.modules.ops.inbox.interfaces import IInboxCommands


class ProcessUpdate(RedisScheduler):
    def __init__(self, commands: IInboxCommands):
        self.commands = commands

    async def run(self, update_id: int) -> None:
        try:
            await self.commands.process(update_id)
        except Exception as error:
            raise RuntimeError(
                "Her task failed: " + type(error).__name__
            ) from None
