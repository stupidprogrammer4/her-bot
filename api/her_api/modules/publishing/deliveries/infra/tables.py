from papilio.infra.db.table import BaseTable
from sqlalchemy import Index, UniqueConstraint

from her_api.modules.publishing.deliveries.domain.models import (
    DeliveryGateModel,
    PublicationJobModel,
)


class PublicationJobTable(PublicationJobModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "kind", "ordinal", name="uq_publication_slot"
        ),
        UniqueConstraint("plan_id", "track_id", name="uq_publication_track"),
        UniqueConstraint(
            "update_id", "write_slot", name="uq_publication_action"
        ),
        Index("ix_publication_due", "status", "next_attempt_at", "id"),
    )


class DeliveryGateTable(DeliveryGateModel, BaseTable, table=True):
    pass
