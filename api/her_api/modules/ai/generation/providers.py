from dishka import Provider, Scope, provide

from her_api.modules.ai.generation.app.commands import GenerationCommands
from her_api.modules.ai.generation.app.concurrency import ModelConcurrency
from her_api.modules.ai.generation.infra.groq import GroqClient
from her_api.modules.ai.generation.infra.mysql import (
    DailyCallRepository,
    ModelCallRepository,
)
from her_api.modules.ai.generation.interfaces import (
    IGenerationCommands,
    IModelClient,
)


class GenerationProvider(Provider):
    scope = Scope.REQUEST
    concurrency = provide(ModelConcurrency, scope=Scope.APP)
    model = provide(GroqClient, provides=IModelClient, scope=Scope.APP)
    calls = provide(ModelCallRepository)
    budget = provide(DailyCallRepository)
    commands = provide(GenerationCommands, provides=IGenerationCommands)
