import pytest

from her_api.modules.library.tracks.interfaces import ITrackService
from her_contracts.media import AudioUpload
from tests.conftest import BOT_ID, OWNER


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reference_case_and_exact_replay_are_preserved(
    native,
):
    async with native.scope() as scope:
        service = await scope.get(ITrackService)
        first = await service.upload(
            AudioUpload(
                bot_id=BOT_ID,
                file_id="FileA",
                file_unique_id="UniqueA",
                source_chat_id=OWNER,
                source_message_id=1,
                duration=10,
            )
        )
        first_id = first.id
        second = await service.upload(
            AudioUpload(
                bot_id=BOT_ID,
                file_id="FileB",
                file_unique_id="uniquea",
                source_chat_id=OWNER,
                source_message_id=2,
                duration=10,
            )
        )
        assert first_id != second.id
    async with native.scope() as scope:
        service = await scope.get(ITrackService)
        replay = await service.upload(
            AudioUpload(
                bot_id=BOT_ID,
                file_id="RefreshedFile",
                file_unique_id="UniqueA",
                source_chat_id=OWNER,
                source_message_id=3,
                duration=10,
            )
        )
        assert replay.id == first_id
    async with native.scope() as scope:
        service = await scope.get(ITrackService)
        page = await service.page(1)
        assert page.total == 2
        assert {t.file_unique_id: t.file_id for t in page.items} == {
            "UniqueA": "RefreshedFile",
            "uniquea": "FileB",
        }
