"""Move the stored model policy to Groq."""

import sqlalchemy as sa
from alembic import op

revision = "20261013_groq_model"
down_revision = "20261011_occasion_catalogue"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            "UPDATE tbl_settings SET value = JSON_SET(value, "
            "'$.model', 'qwen/qwen3.8-27b', '$.reasoning_effort', NULL), "
            "revision = revision + 1 WHERE `key` = 'model'"
        )
    )


def downgrade():
    raise RuntimeError("Restore the model policy from a pre-migration backup")
