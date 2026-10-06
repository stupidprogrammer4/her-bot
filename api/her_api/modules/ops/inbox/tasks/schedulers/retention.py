from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from her_api.modules.content.channel.interfaces import IChannelCommands
from her_api.modules.conversations.chat.interfaces import IChatCommands
from her_api.modules.ops.inbox.interfaces import IInboxCommands
from her_api.modules.publishing.deliveries.interfaces import (
    IPublicationCommands,
)


class ApplyRetention(RedisScheduler):
    schedule = [{"interval": 60}]

    def __init__(
        self,
        chat: IChatCommands,
        inbox: IInboxCommands,
        publications: IPublicationCommands,
        channel: IChannelCommands,
    ):
        self.chat, self.inbox, self.publications, self.channel = (
            chat,
            inbox,
            publications,
            channel,
        )

    async def run(self) -> None:
        try:
            await self.chat.purge()
            await self.inbox.purge()
            await self.publications.purge()
            await self.channel.purge()
        except Exception as error:
            raise RuntimeError(
                "Her task failed: " + type(error).__name__
            ) from None
