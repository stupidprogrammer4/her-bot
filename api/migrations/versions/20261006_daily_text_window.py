"""Preserve text and music opening times independently."""

from alembic import op
from sqlalchemy import Column, DateTime

revision = "20261006_daily_text"
down_revision = "20261006_import_replay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_plans", Column("text_starts_at", DateTime(), nullable=True)
    )
    op.execute("UPDATE tbl_plans SET text_starts_at=starts_at")


def downgrade() -> None:
    op.drop_column("tbl_plans", "text_starts_at")
