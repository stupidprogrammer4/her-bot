from papilio.infra.db.table import BaseTable
from sqlalchemy import UniqueConstraint

from her_api.modules.publishing.plans.domain.models import PlanModel


class PlanTable(PlanModel, BaseTable, table=True):
    __table_args__ = (
        UniqueConstraint("channel_id", "evening_date", name="uq_plan_evening"),
    )
