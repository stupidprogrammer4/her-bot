from papilio.infra.db.table import BaseTable

from her_api.modules.library.tracks.domain.models import TrackModel


class TrackTable(TrackModel, BaseTable, table=True):
    pass
