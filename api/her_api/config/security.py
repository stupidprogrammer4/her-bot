from hmac import compare_digest

from fastapi import Header, HTTPException
from papilio.core.config import get_settings

from her_api.config.settings import HerSettings


def service_auth(authorization: str = Header(default="")) -> None:
    settings = get_settings(HerSettings)
    expected = "Bearer " + settings.security.service_key.get_secret_value()
    if not compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(401, "Unauthorized")
