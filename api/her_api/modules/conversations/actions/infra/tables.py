from papilio.infra.db.table import BaseTable

from her_api.modules.conversations.actions.domain.models import (
    DeleteConfirmationModel,
    OwnerActionModel,
)


class OwnerActionTable(OwnerActionModel, BaseTable, table=True):
    pass


class DeleteConfirmationTable(DeleteConfirmationModel, BaseTable, table=True):
    pass
