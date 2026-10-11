"""Add source-backed editable occasions."""

import json
from importlib.resources import files

import sqlalchemy as sa
from alembic import op

revision = "20261011_occasion_catalogue"
down_revision = "20261006_daily_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        "tbl_occasions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    entries = json.loads(
        files("amupouya_calendar")
        .joinpath("data", "catalogue_20261011.json")
        .read_text()
    )
    op.bulk_insert(
        table,
        [
            dict(
                key=e["id"],
                definition=json.dumps(e, ensure_ascii=False),
                enabled=True,
                revision=1,
            )
            for e in entries
        ],
    )

    op.add_column(
        "tbl_plans",
        sa.Column("occasion_created_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "tbl_publication_jobs",
        sa.Column("occasion_json", sa.Text(), nullable=True),
    )
    policy = {
        "enabled": True,
        "selection": "all",
        "tags": ["girls", "women", "friendship", "relationship", "motherhood"],
        "time": "10:00:00",
        "catchup_until": "23:00:00",
        "prompt": (
            "به مناسبت\u200cهای امروز واکنش شخصی و کوتاه نشان "
            "بده، مثل دیلی خودت؛ صمیمی، دخترانه و طبیعی، نه گزارش "
            "رسمی و نه نقش ریک. اسم هر مناسبت را دقیقاً یک\u200cبار در "
            "متن بیاور. مناسبت غیررسمی را رسمی یا جهانی جا نزن. "
            "برای روزهای خشونت و تبعیض همدلانه بنویس؛ شوخی و تبریک "
            "نامناسب نکن. دربارهٔ زندگی واقعی یا خاطرهٔ شخصی چیزی "
            "نساز. یک تا سه ایموجی مرتبط کافی است. فقط متن نهایی "
            "فارسی."
        ),
        "fallback_template": (
            "امروز {titles}ه. خواستم این گوشه از دیلیم یادش بمونه 🕯️🤍"
        ),
    }
    op.get_bind().execute(
        sa.text(
            "INSERT INTO tbl_settings (`key`,value,revision) "
            "VALUES ('occasions',:value,1) "
            "ON DUPLICATE KEY UPDATE `key`=`key`"
        ),
        {"value": json.dumps(policy, ensure_ascii=False)},
    )


def downgrade() -> None:
    op.drop_column("tbl_plans", "occasion_created_at")
    op.drop_column("tbl_publication_jobs", "occasion_json")
    op.drop_table("tbl_occasions")
