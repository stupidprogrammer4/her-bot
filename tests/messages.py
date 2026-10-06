from datetime import UTC, datetime

from her_contracts.telegram import IncomingMessage
from tests.conftest import OWNER


def message(update_id: int, text: str, **changes) -> IncomingMessage:
    return IncomingMessage(
        update_id=update_id,
        message_id=update_id + 1,
        chat_id=OWNER,
        sender_id=OWNER,
        chat_type="private",
        text=text,
        addressed=True,
        posted_at=datetime.now(UTC),
        **changes,
    )
