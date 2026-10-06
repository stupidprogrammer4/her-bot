"""Preserve editable persona policies larger than MySQL TEXT."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.mysql import LONGTEXT

revision = "20261006_settings_payload"
down_revision = "20261006_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tbl_settings",
        "value",
        existing_type=sa.Text(),
        type_=LONGTEXT(),
        existing_nullable=False,
    )


def downgrade() -> None:
    raise RuntimeError("Export large persona policies before restoring TEXT")
