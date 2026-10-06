from datetime import datetime

from papilio.infra.db.repositories.backends.mysql import MySQLReader
from sqlalchemy import func, select
from sqlmodel import col

from her_api.modules.conversations.chat.domain.dtos import (
    ConversationAdmission,
)
from her_api.modules.conversations.chat.infra.tables import ChatRequestTable


class ConversationReader(MySQLReader):
    async def admission(
        self, user_id: int, since: datetime
    ) -> ConversationAdmission:
        result = await self.uow.execute(
            select(
                func.count(col(ChatRequestTable.id)),
                func.max(col(ChatRequestTable.created_at)),
            ).where(
                col(ChatRequestTable.user_id) == user_id,
                col(ChatRequestTable.created_at) >= since,
            )
        )
        count, latest = result.one()
        return ConversationAdmission(hourly_count=count, latest_at=latest)
