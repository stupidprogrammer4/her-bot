import json
from datetime import UTC, datetime
from typing import Any

from her_contracts.channel import ChannelPostWrite


class TelegramExportParser:
    def flatten(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "".join(
                item
                if isinstance(item, str)
                else item.get("text", "")
                if isinstance(item, dict) and isinstance(item.get("text"), str)
                else ""
                for item in value
            )
        return ""

    def parse(
        self, raw: str, channel_id: int
    ) -> tuple[list[ChannelPostWrite], int, bool, str]:
        if len(raw.encode()) > 10 * 1024 * 1024:
            raise ValueError("Import exceeds 10 MB")
        try:
            data = json.loads(raw)
            export_id = int(data.get("id", 0))
            matching = (
                export_id == channel_id
                or abs(export_id) == abs(channel_id)
                or int("-100" + str(abs(export_id))) == channel_id
            )
            messages = data["messages"]
            if not isinstance(messages, list) or len(messages) > 50000:
                raise ValueError("Invalid export messages")
            rows, invalid = [], 0
            for message in messages:
                try:
                    if message.get("type") != "message":
                        continue
                    stamp = datetime.fromtimestamp(
                        int(message["date_unixtime"]), UTC
                    )
                    text = self.flatten(message.get("text", ""))
                    if (
                        len(text) > 10000
                        or stamp.year < 2000
                        or stamp.year > datetime.now(UTC).year + 1
                    ):
                        raise ValueError("Invalid exported message")
                    rows.append(
                        ChannelPostWrite(
                            channel_id=channel_id,
                            message_id=message["id"],
                            text=text,
                            posted_at=stamp,
                            media_kind="media"
                            if "media_type" in message
                            else "text",
                            origin="imported"
                            if matching
                            else "imported_unverified_mapping",
                        )
                    )
                except (
                    KeyError,
                    ValueError,
                    TypeError,
                    AttributeError,
                    OverflowError,
                    OSError,
                ):
                    invalid += 1
            return rows, invalid, matching, str(data.get("name", ""))[:200]
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ValueError(
                "Invalid Telegram Desktop channel export"
            ) from None
