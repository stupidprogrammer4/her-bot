from datetime import datetime, timedelta
from typing import Any, cast

from papilio.infra.db.repositories.backends.mysql import MySQLRepository
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.sql.elements import ColumnClause
from sqlmodel import col

from her_api.modules.conversations.chat.domain.dtos import ChatChange
from her_api.modules.conversations.chat.domain.models import (
    ChatRequestModel,
    ConversationModel,
    ConversationPairModel,
)
from her_api.modules.conversations.chat.infra.tables import (
    ChatRequestTable,
    ConversationPairTable,
    ConversationTable,
)


class ConversationRepository(MySQLRepository[ConversationModel]):
    table = ConversationTable

    async def acquire(
        self, chat_id: int, user_id: int, request_id: int, now: datetime
    ) -> bool:
        await self.upsert(
            ConversationModel(chat_id=chat_id, user_id=user_id),
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.chat_id) == chat_id,
                col(self.table.user_id) == user_id,
                col(self.table.active_request_id).is_(None)
                | (col(self.table.active_request_id) == request_id)
                | (col(self.table.lease_expires_at) <= now),
            )
            .values(
                active_request_id=request_id,
                lease_expires_at=now + timedelta(seconds=90),
            )
        )
        return cast(CursorResult, result).rowcount == 1

    async def release(
        self, chat_id: int, user_id: int, request_id: int
    ) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.chat_id) == chat_id,
                col(self.table.user_id) == user_id,
                col(self.table.active_request_id) == request_id,
            )
            .values(active_request_id=None, lease_expires_at=None)
        )


class ChatRequestRepository(MySQLRepository[ChatRequestModel]):
    table = ChatRequestTable

    async def admit(self, data: ChatRequestModel) -> None:
        await self.upsert(
            data,
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )

    async def get(self, id: int) -> ChatRequestModel | None:
        result = await self.uow.execute(
            select(self.table)
            .where(col(self.table.id) == id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def claim(self, id: int, now: datetime) -> bool:
        result = await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.id) == id,
                col(self.table.status) == "pending",
                col(self.table.next_attempt_at) <= now,
            )
            .values(
                status="running", lease_expires_at=now + timedelta(seconds=90)
            )
        )
        return cast(CursorResult, result).rowcount == 1

    async def change(self, id: int, change: ChatChange) -> None:
        await self.uow.execute(
            update(self.table)
            .where(col(self.table.id) == id)
            .values(**change.model_dump(exclude_unset=True))
        )

    async def recover(self, now: datetime) -> list[int]:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.status) == "running",
                col(self.table.lease_expires_at) <= now,
            )
            .values(status="pending", lease_expires_at=None)
        )
        result = await self.uow.execute(
            select(col(self.table.id))
            .where(
                col(self.table.status) == "pending",
                col(self.table.next_attempt_at) <= now,
            )
            .order_by(col(self.table.id))
            .limit(30)
        )
        return list(result.scalars())

    async def forget(self, chat_id: int, user_id: int) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.chat_id) == chat_id,
                col(self.table.user_id) == user_id,
            )
            .values(text="", messages="[]", status="forgotten")
        )

    async def purge(self, before: datetime) -> None:
        await self.uow.execute(
            update(self.table)
            .where(
                col(self.table.created_at) < before,
                col(self.table.status).in_(["completed", "forgotten"]),
            )
            .values(text="", messages="[]")
        )


class ConversationPairRepository(MySQLRepository[ConversationPairModel]):
    table = ConversationPairTable

    async def save(self, data: ConversationPairModel) -> None:
        await self.upsert(
            data,
            update_columns=[],
            changes={
                cast(ColumnClause[Any], col(self.table.id)): col(self.table.id)
            },
        )

    async def history(
        self, chat_id: int, user_id: int, before: datetime, limit: int
    ) -> list[ConversationPairModel]:
        result = await self.uow.execute(
            select(self.table)
            .where(
                col(self.table.chat_id) == chat_id,
                col(self.table.user_id) == user_id,
                col(self.table.created_at) >= before,
            )
            .order_by(col(self.table.id).desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def forget(self, chat_id: int, user_id: int) -> None:
        await self.uow.execute(
            delete(self.table).where(
                col(self.table.chat_id) == chat_id,
                col(self.table.user_id) == user_id,
            )
        )

    async def purge(self, before: datetime) -> None:
        await self.uow.execute(
            delete(self.table).where(col(self.table.created_at) < before)
        )
