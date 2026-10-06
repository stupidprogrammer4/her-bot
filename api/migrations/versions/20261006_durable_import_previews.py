"""Keep import previews and private responses stable across polling replay."""

from alembic import op
from sqlalchemy import BigInteger, Column, Text

revision = "20261006_import_replay"
down_revision = "20261006_reference_case"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tbl_channel_imports", Column("update_id", BigInteger(), nullable=True)
    )
    op.add_column(
        "tbl_channel_imports",
        Column("preview_json", Text(), nullable=True),
    )
    op.execute(
        "UPDATE tbl_channel_imports SET preview_json='' "
        "WHERE preview_json IS NULL"
    )
    op.alter_column(
        "tbl_channel_imports",
        "preview_json",
        existing_type=Text(),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_channel_import_update", "tbl_channel_imports", ["update_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_channel_import_update", "tbl_channel_imports", type_="unique"
    )
    op.drop_column("tbl_channel_imports", "preview_json")
    op.drop_column("tbl_channel_imports", "update_id")
