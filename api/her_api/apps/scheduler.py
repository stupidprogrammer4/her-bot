import os

from dotenv import load_dotenv
from papilio.core.config import get_settings
from papilio_tasks.apps.schedulers.redis import create_app

from her_api.config.providers import task_providers
from her_api.config.settings import HerSettings

load_dotenv(os.getenv("HER_ENV_FILE", ".env"))
settings = get_settings(HerSettings)
app = create_app(
    settings.tasks,
    providers=task_providers(settings),
    modules=settings.app.modules,
)
broker, scheduler = app.broker, app.scheduler
