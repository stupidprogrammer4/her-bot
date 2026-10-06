import httpx

from her_bot.config.settings import BotSettings
from her_contracts.channel import ImportPreview
from her_contracts.telegram import BotConfiguration, IncomingMessage


class BackendUnavailable(Exception):
    pass


class BackendRejected(ValueError):
    pass


class Backend:
    def __init__(self, http: httpx.AsyncClient, settings: BotSettings):
        self.http, self.settings = http, settings
        self.headers = {
            "Authorization": "Bearer "
            + settings.service_key.get_secret_value()
        }

    async def configuration(self) -> BotConfiguration:
        try:
            response = await self.http.get(
                self.settings.backend_url + "/internal/configuration",
                headers=self.headers,
            )
            response.raise_for_status()
            result = BotConfiguration.model_validate(response.json())
        except (httpx.HTTPError, ValueError):
            raise BackendUnavailable("Configuration unavailable") from None
        return result

    async def admit(self, data: IncomingMessage) -> None:
        try:
            response = await self.http.post(
                self.settings.backend_url + "/internal/updates",
                headers=self.headers,
                json=data.model_dump(mode="json"),
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise BackendUnavailable("Update not durably accepted") from None

    async def import_preview(
        self,
        raw: str,
        actor_id: int,
        chat_id: int,
        update_id: int,
        message_id: int,
    ) -> ImportPreview:
        try:
            response = await self.http.post(
                self.settings.backend_url + "/internal/channel/import",
                headers=self.headers,
                json={
                    "raw": raw,
                    "actor_id": actor_id,
                    "chat_id": chat_id,
                    "update_id": update_id,
                    "message_id": message_id,
                },
                timeout=30,
            )
            if response.status_code in {400, 403, 413, 422}:
                raise BackendRejected("Export rejected")
            response.raise_for_status()
            preview = ImportPreview.model_validate(response.json())
        except BackendRejected:
            raise
        except (httpx.HTTPError, ValueError):
            raise BackendUnavailable("Import unavailable") from None
        return preview

    async def import_open(self, actor_id: int) -> bool:
        try:
            response = await self.http.get(
                self.settings.backend_url
                + "/internal/channel/import/"
                + str(actor_id),
                headers=self.headers,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise BackendUnavailable("Import mode unavailable") from None
        return response.json().get("open") is True

    async def heartbeat(self) -> None:
        try:
            response = await self.http.post(
                self.settings.backend_url + "/internal/channel/heartbeat",
                headers=self.headers,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise BackendUnavailable("Heartbeat unavailable") from None
