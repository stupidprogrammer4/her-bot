from papilio.infra.db.table import BaseTable
from sqlalchemy import Index, UniqueConstraint

from her_api.modules.conversations.chat.domain.models import (
    ChatRequestModel,
    ConversationModel,
    ConversationPairModel,
)


class ConversationTable(ConversationModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_conversation_scope"),
    )


class ChatRequestTable(ChatRequestModel, BaseTable, table=True):
    __table_args__ = (
        Index("ix_chat_request_due", "status", "next_attempt_at"),
        Index("ix_chat_rate", "user_id", "created_at"),
    )


class ConversationPairTable(ConversationPairModel, BaseTable, table=True):
    __table_args__ = (
        Index("ix_conversation_history", "chat_id", "user_id", "created_at"),
    )
