from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from papilio.infra.redis.client import RedisClient, resolve

from her_api.modules.ops.inbox.interfaces import IInboxCommands

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("native", [False], indirect=True)
async def test_retention_preserves_pending_unread_and_recent_tasks(native):
    native.settings.tasks = replace(
        native.settings.tasks,
        queue_name=native.settings.tasks.queue_name + ":retention",
    )
    stream = native.settings.tasks.queue_name
    now = datetime.now(UTC)
    native.clock.instant = now
    old = int((now - timedelta(hours=2)).timestamp() * 1000)
    ids = [f"{old}-{n}" for n in range(3)]
    recent = f"{int(now.timestamp() * 1000)}-0"
    async with native.scope() as scope:
        redis = (await scope.get(RedisClient)).client
        await resolve(redis.xadd(stream, {"data": "completed"}, id=ids[0]))
        await resolve(redis.xadd(stream, {"data": "pending"}, id=ids[1]))
        await resolve(redis.xadd(stream, {"data": "unread"}, id=ids[2]))
        await resolve(redis.xadd(stream, {"data": "recent"}, id=recent))
        await resolve(redis.xgroup_create(stream, "first", id="0"))
        await resolve(redis.xgroup_create(stream, "second", id="0"))
        await resolve(
            redis.xreadgroup("first", "reader", {stream: ">"}, count=2)
        )
        await resolve(
            redis.xreadgroup("second", "reader", {stream: ">"}, count=2)
        )
        await resolve(redis.xack(stream, "first", *ids[:2]))
        await resolve(redis.xack(stream, "second", ids[0]))
        await (await scope.get(IInboxCommands)).purge()
        remaining = await resolve(redis.xrange(stream))
        pending = await resolve(redis.xpending(stream, "second"))
    assert [entry[0] for entry in remaining] == [ids[1], ids[2], recent]
    assert pending["pending"] == 1
