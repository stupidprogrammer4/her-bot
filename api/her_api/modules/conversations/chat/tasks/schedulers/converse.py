from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from her_api.modules.conversations.chat.interfaces import IChatCommands


class Converse(RedisScheduler):
    def __init__(self, commands: IChatCommands):
        self.commands = commands

    async def run(self, request_id: int) -> None:
        try:
            again = await self.commands.step(request_id)
            if again:
                await Converse.enqueue(request_id)
        except Exception as error:
            raise RuntimeError(
                "Her task failed: " + type(error).__name__
            ) from None
