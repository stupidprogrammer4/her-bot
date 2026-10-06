"""Keep Telegram references and confirmation tokens case sensitive."""

from alembic import op
from sqlalchemy import String

revision = "20261006_reference_case"
down_revision = "20261006_settings_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table, column, length in (
        ("tbl_tracks", "file_id", 512),
        ("tbl_tracks", "file_unique_id", 128),
        ("tbl_channel_imports", "token", 64),
        ("tbl_delete_confirmations", "token", 64),
    ):
        op.alter_column(
            table,
            column,
            existing_type=String(length),
            type_=String(length, collation="utf8mb4_bin"),
            existing_nullable=False,
        )


def downgrade() -> None:
    raise RuntimeError(
        "Case-insensitive references can merge distinct records"
    )
