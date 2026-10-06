from dishka import Provider, Scope, provide

from her_api.modules.persona.privacy.app.guard import IdentityGuard


class PrivacyProvider(Provider):
    scope = Scope.APP
    guard = provide(IdentityGuard)
