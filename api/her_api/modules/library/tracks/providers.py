from dishka import Provider, Scope, provide

from her_api.modules.library.tracks.app.services import TrackService
from her_api.modules.library.tracks.infra.mysql import TrackRepository
from her_api.modules.library.tracks.interfaces import ITrackService


class TracksProvider(Provider):
    scope = Scope.REQUEST
    repo = provide(TrackRepository)
    service = provide(TrackService, provides=ITrackService)
