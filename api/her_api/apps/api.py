import os

from dotenv import load_dotenv
from fastapi.exceptions import RequestValidationError
from papilio.api.application import create_app
from papilio.core.config import get_settings
from papilio.errors.exceptions import NotFoundException
from papilio_tasks.apps.lifecycle import Producers

from her_api.apps.scheduler import app as tasks
from her_api.config.errors import (
    internal_failure,
    invalid_operation,
    invalid_request,
    missing_record,
)
from her_api.config.providers import infrastructure_providers
from her_api.config.settings import HerSettings

load_dotenv(os.getenv("HER_ENV_FILE", ".env"))
settings = get_settings(HerSettings)
app = create_app(
    settings,
    providers=infrastructure_providers(settings),
    middleware=[],
    lifespan=Producers(tasks),
    exception_handlers={
        ValueError: invalid_operation,
        NotFoundException: missing_record,
        RequestValidationError: invalid_request,
        Exception: internal_failure,
    },
    docs_url=None,
)
