from papilio.infra.db.table import BaseTable

from her_api.modules.content.occasions.domain.models import OccasionModel


class OccasionTable(OccasionModel, BaseTable, table=True):
    pass
