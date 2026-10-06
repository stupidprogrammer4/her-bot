from papilio.infra.db.table import BaseTable

from her_api.modules.ops.settings.domain.models import SettingModel


class SettingTable(SettingModel, BaseTable, table=True):
    pass
