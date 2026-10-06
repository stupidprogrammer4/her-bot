import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from her_api.modules.content.channel.interfaces import (
    IChannelCommands,
    IChannelQueries,
)
from her_bot.infra.backend import BackendRejected
from her_contracts.channel import ChannelPostWrite
from tests.conftest import CHANNEL, OWNER
from tests.messages import message

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def export(count: int, id: int = CHANNEL) -> str:
    return json.dumps(
        {
            "id": id,
            "name": "Test channel",
            "messages": [
                {
                    "type": "message",
                    "id": 900 + i,
                    "date_unixtime": str(
                        int(datetime.now(UTC).timestamp()) - i
                    ),
                    "text": [{"type": "bold", "text": "متن زمینه "}, str(i)],
                }
                for i in range(count)
            ],
        },
        ensure_ascii=False,
    )


async def test_import_replay_keeps_preview_and_private_reply_atomic(native):
    await native.post(message(701, "/import_channel"))
    first, second = await asyncio.gather(
        native.backend.import_preview(export(2), OWNER, OWNER, 702, 703),
        native.backend.import_preview(export(2), OWNER, OWNER, 702, 703),
    )
    assert first.token == second.token
    reply = await native.services.received(
        lambda request: "پیش‌نمایش ورود تاریخچه" in request.get("text", "")
    )
    assert first.token in reply["text"]
    assert json.loads(reply["reply_parameters"])["message_id"] == 703
    assert (
        len(
            await native.rows(
                "SELECT id FROM tbl_channel_imports WHERE update_id=702"
            )
        )
        == 1
    )
    assert (
        len(
            await native.rows(
                "SELECT id FROM tbl_publication_jobs WHERE update_id=702"
            )
        )
        == 1
    )
    with pytest.raises(BackendRejected):
        await native.backend.import_preview("not json", OWNER, OWNER, 704, 705)


async def test_import_requires_owner_and_mapping_before_atomic_confirmation(
    native,
):
    async with native.scope() as scope:
        commands = await scope.get(IChannelCommands)
        await commands.start_import(OWNER)
        preview = await commands.import_preview(export(2, id=123456), OWNER)
    assert preview.count == 2 and not preview.matching_channel
    assert not await native.rows("SELECT id FROM tbl_channel_posts")
    async with native.scope() as scope:
        commands = await scope.get(IChannelCommands)
        with pytest.raises(ValueError):
            await commands.import_confirm(preview.token, OWNER)
    async with native.scope() as scope:
        commands = await scope.get(IChannelCommands)
        with pytest.raises(ValueError):
            await commands.import_confirm(preview.token, 22222, True)

    async def confirm() -> int:
        async with native.scope() as scope:
            commands = await scope.get(IChannelCommands)
            count = await commands.import_confirm(preview.token, OWNER, True)
        return count

    counts = await asyncio.gather(confirm(), confirm())
    assert sorted(counts) == [0, 2]
    rows = await native.rows(
        "SELECT origin,text FROM tbl_channel_posts ORDER BY message_id"
    )
    assert len(rows) == 2 and {r["origin"] for r in rows} == {
        "imported_unverified_mapping"
    }
    assert not any(
        int(r.get("chat_id", 0)) == CHANNEL
        for r in native.services.telegram_requests
    )
    async with native.scope() as scope:
        queries = await scope.get(IChannelQueries)
        context = await queries.context()
    assert context.last_update_received_at is None
    assert context.unknown_deletions and context.gaps


async def test_large_export_survives_mysql_and_import_replay(
    native,
):
    raw = export(800)
    assert len(raw.encode()) > 65535
    async with native.scope() as scope:
        commands = await scope.get(IChannelCommands)
        await commands.start_import(OWNER)
        preview = await commands.import_preview(raw, OWNER)
    async with native.scope() as scope:
        commands = await scope.get(IChannelCommands)
        count = await commands.import_confirm(preview.token, OWNER)
    assert count == 800
    async with native.scope() as scope:
        commands = await scope.get(IChannelCommands)
        assert await commands.import_confirm(preview.token, OWNER) == 0
    assert (
        await native.rows("SELECT COUNT(*) AS count FROM tbl_channel_posts")
    )[0]["count"] == 800


async def test_live_edits_and_context_removal_preserve_telegram(
    native,
):
    now = datetime.now(UTC)
    async with native.scope() as scope:
        commands = await scope.get(IChannelCommands)
        await commands.observe(
            ChannelPostWrite(
                channel_id=CHANNEL,
                message_id=500,
                text="متن اول",
                posted_at=now,
            )
        )
        await commands.observe(
            ChannelPostWrite(
                channel_id=CHANNEL,
                message_id=500,
                text="نام فرضی متن ویرایش",
                posted_at=now,
                edited_at=now,
            )
        )
    rows = await native.rows(
        "SELECT text FROM tbl_channel_posts WHERE message_id=500"
    )
    assert len(rows) == 1 and "نام فرضی" not in rows[0]["text"]
    async with native.scope() as scope:
        queries = await scope.get(IChannelQueries)
        context = await queries.context(query="ویرایش")
        assert (
            len(context.posts) == 1
            and context.last_update_received_at is not None
        )
        commands = await scope.get(IChannelCommands)
        await commands.deactivate(500)
    async with native.scope() as scope:
        queries = await scope.get(IChannelQueries)
        assert not (await queries.context()).posts
    assert not any(
        r.get("method") == "deleteMessage"
        for r in native.services.telegram_requests
    )


async def test_retention_preserves_ledger_and_expires_import(
    native,
):
    now = datetime.now(UTC)
    async with native.scope() as scope:
        commands = await scope.get(IChannelCommands)
        await commands.start_import(OWNER)
        preview = await commands.import_preview(export(1), OWNER)
        await commands.observe(
            ChannelPostWrite(
                channel_id=CHANNEL,
                message_id=499,
                text="old",
                posted_at=now - timedelta(days=91),
            )
        )
    await native.execute(
        "UPDATE tbl_channel_imports SET expires_at=:time WHERE token=:token",
        {"time": now - timedelta(seconds=1), "token": preview.token},
    )
    async with native.scope() as scope:
        commands = await scope.get(IChannelCommands)
        await commands.purge()
    assert not await native.rows(
        "SELECT id FROM tbl_channel_posts WHERE message_id=499"
    )
    assert (
        await native.rows(
            (
                "SELECT payload,status FROM tbl_channel_imports "
                "WHERE token=:token"
            ),
            {"token": preview.token},
        )
    ) == [{"payload": "[]", "status": "expired"}]
    assert await native.rows("SHOW TABLES LIKE 'tbl_publication_jobs'")
