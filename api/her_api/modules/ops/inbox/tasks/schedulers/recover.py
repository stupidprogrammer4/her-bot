import asyncio

from papilio_tasks.apps.schedulers.backends.redis import RedisScheduler

from her_api.modules.conversations.chat.interfaces import IChatCommands
from her_api.modules.conversations.chat.tasks.schedulers.converse import (
    Converse,
)
from her_api.modules.ops.inbox.interfaces import IInboxCommands
from her_api.modules.ops.inbox.tasks.schedulers.process import ProcessUpdate
from her_api.modules.publishing.deliveries.interfaces import (
    IPublicationCommands,
)
from her_api.modules.publishing.deliveries.tasks.schedulers.deliver import (
    Deliver,
)
from her_api.modules.publishing.plans.interfaces import IPlanCommands


class RecoverWork(RedisScheduler):
    schedule = [{"interval": 2}]

    def __init__(
        self,
        plans: IPlanCommands,
        publications: IPublicationCommands,
        inbox: IInboxCommands,
        chat: IChatCommands,
    ):
        self.plans, self.publications, self.inbox, self.chat = (
            plans,
            publications,
            inbox,
            chat,
        )

    async def run(self) -> None:
        try:
            await self.plans.prepare()
            job_ids = await self.publications.recover()
            updates = await self.inbox.recover()
            chats = await self.chat.recover()
            await asyncio.gather(
                *(Deliver.enqueue(id) for id in job_ids),
                *(ProcessUpdate.enqueue(id) for id in updates),
                *(Converse.enqueue(id) for id in chats),
            )
        except Exception as error:
            raise RuntimeError(
                "Her task failed: " + type(error).__name__
            ) from None
