from papilio.infra.db.table import BaseTable

from her_api.modules.ops.inbox.domain.models import InboxModel


class InboxTable(InboxModel, BaseTable, table=True):
    pass
