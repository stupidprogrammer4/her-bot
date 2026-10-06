from her_api.modules.content.channel.infra.readers import ChannelReader
from her_api.modules.ops.settings.interfaces import ISettingsQueries
from her_contracts.channel import ChannelContext


class ChannelQueries:
    def __init__(self, reader: ChannelReader, settings: ISettingsQueries):
        self.reader, self.settings = reader, settings

    async def context(
        self, limit: int | None = None, query: str | None = None
    ) -> ChannelContext:
        settings = await self.settings.snapshot()
        if query and len(query) > 100:
            raise ValueError("Query too long")
        rows = await self.reader.context(
            settings.access.channel_id,
            min(limit or settings.model.context_limit, 30),
            settings.model.context_chars,
            query,
        )
        return rows
