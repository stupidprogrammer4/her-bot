from papilio.infra.db.table import BaseTable
from sqlalchemy import Index, UniqueConstraint

from her_api.modules.content.channel.domain.models import (
    ChannelCoverageModel,
    ChannelImportModel,
    ChannelPostModel,
    ImportSessionModel,
)


class ChannelPostTable(ChannelPostModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_channel_post"),
        Index("ix_channel_context", "channel_id", "posted_at", "message_id"),
    )


class ChannelImportTable(ChannelImportModel, BaseTable, table=True):
    pass


class ImportSessionTable(ImportSessionModel, BaseTable, table=True):
    pass


class ChannelCoverageTable(ChannelCoverageModel, BaseTable, table=True):
    pass
