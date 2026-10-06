import httpx

from her_api.config.settings import HerSettings
from her_contracts.publications import Receipt, TelegramSend


class TelegramTransport:
    def __init__(self, http: httpx.AsyncClient, settings: HerSettings):
        self.http, self.settings = http, settings

    async def send(self, data: TelegramSend) -> Receipt:
        try:
            response = await self.http.post(
                self.settings.telegram.gateway_url + "/internal/send",
                json=data.model_dump(mode="json"),
                headers={
                    "Authorization": "Bearer "
                    + self.settings.security.service_key.get_secret_value()
                },
                timeout=httpx.Timeout(30, connect=5),
            )
            if response.status_code != 200:
                return Receipt(
                    status="delivery_unknown",
                    reason="gateway_response_unknown",
                )
            receipt = Receipt.model_validate(response.json())
        except (httpx.RequestError, ValueError):
            return Receipt(
                status="delivery_unknown", reason="gateway_delivery_unknown"
            )
        return receipt
