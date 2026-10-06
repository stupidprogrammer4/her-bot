from papilio.infra.db.table import BaseTable

from her_api.modules.ai.generation.domain.models import (
    DailyCallModel,
    ModelCallModel,
)


class DailyCallTable(DailyCallModel, BaseTable, table=True):
    pass


class ModelCallTable(ModelCallModel, BaseTable, table=True):
    pass
