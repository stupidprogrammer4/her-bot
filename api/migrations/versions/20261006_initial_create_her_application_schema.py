"""Create Her application schema"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20261006_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tbl_channel_coverages",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "last_update_received_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_heartbeat_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("gaps_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id"),
    )
    op.create_table(
        "tbl_channel_imports",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", mysql.LONGTEXT(), nullable=False),
        sa.Column("matching_channel", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_table(
        "tbl_channel_posts",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("media_kind", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel_id", "message_id", name="uq_channel_post"
        ),
    )
    op.create_index(
        "ix_channel_context",
        "tbl_channel_posts",
        ["channel_id", "posted_at", "message_id"],
        unique=False,
    )
    op.create_table(
        "tbl_chat_requests",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("private_owner", sa.Boolean(), nullable=False),
        sa.Column("authenticated_owner", sa.Boolean(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("messages", mysql.LONGTEXT(), nullable=False),
        sa.Column("capabilities", sa.Text(), nullable=False),
        sa.Column("phase", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("tool_cursor", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "next_attempt_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "lease_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("update_id"),
    )
    op.create_index(
        "ix_chat_rate",
        "tbl_chat_requests",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_chat_request_due",
        "tbl_chat_requests",
        ["status", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_chat_requests_status"),
        "tbl_chat_requests",
        ["status"],
        unique=False,
    )
    op.create_table(
        "tbl_conversation_pairs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("request_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("user_text", sa.Text(), nullable=False),
        sa.Column("assistant_text", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index(
        "ix_conversation_history",
        "tbl_conversation_pairs",
        ["chat_id", "user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "tbl_conversations",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("active_request_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "lease_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chat_id", "user_id", name="uq_conversation_scope"
        ),
    )
    op.create_table(
        "tbl_daily_calls",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day"),
    )
    op.create_table(
        "tbl_delete_confirmations",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_table(
        "tbl_delivery_gates",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id"),
    )
    op.create_table(
        "tbl_import_sessions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id"),
    )
    op.create_table(
        "tbl_inboxes",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "lease_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("update_id"),
    )
    op.create_index(
        op.f("ix_tbl_inboxes_status"), "tbl_inboxes", ["status"], unique=False
    )
    op.create_table(
        "tbl_model_calls",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("model", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tbl_owner_actions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("write_slot", sa.Integer(), nullable=False),
        sa.Column("capability", sa.String(length=40), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("update_id"),
    )
    op.create_table(
        "tbl_plans",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("evening_date", sa.Date(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("music_status", sa.String(length=24), nullable=False),
        sa.Column("text_count", sa.Integer(), nullable=True),
        sa.Column("text_min_snapshot", sa.Integer(), nullable=False),
        sa.Column("text_max_snapshot", sa.Integer(), nullable=False),
        sa.Column(
            "text_created_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("bootstrap_partial", sa.Boolean(), nullable=False),
        sa.Column("warned_missing_tracks", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel_id", "evening_date", name="uq_plan_evening"
        ),
    )
    op.create_table(
        "tbl_settings",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "tbl_tracks",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", sa.String(length=512), nullable=False),
        sa.Column("file_unique_id", sa.String(length=128), nullable=False),
        sa.Column("source_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("source_message_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("performer", sa.String(length=300), nullable=False),
        sa.Column("filename", sa.String(length=300), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mood", sa.String(length=16), nullable=False),
        sa.Column("tags_json", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_unique_id"),
    )
    op.create_table(
        "tbl_publication_jobs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.Identity(always=False),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("plan_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("track_id", sa.BigInteger(), nullable=True),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("automatic", sa.Boolean(), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=True),
        sa.Column("write_slot", sa.Integer(), nullable=True),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "next_attempt_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "preparing_started_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "send_started_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("target_message_id", sa.Integer(), nullable=True),
        sa.Column("parent_job_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "lease_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("failure_reason", sa.String(length=120), nullable=True),
        sa.Column(
            "retry_confirmation_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["parent_job_id"],
            ["tbl_publication_jobs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["tbl_plans.id"],
        ),
        sa.ForeignKeyConstraint(
            ["track_id"],
            ["tbl_tracks.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_job_id"),
        sa.UniqueConstraint(
            "plan_id", "kind", "ordinal", name="uq_publication_slot"
        ),
        sa.UniqueConstraint(
            "plan_id", "track_id", name="uq_publication_track"
        ),
        sa.UniqueConstraint(
            "update_id", "write_slot", name="uq_publication_action"
        ),
    )
    op.create_index(
        "ix_publication_due",
        "tbl_publication_jobs",
        ["status", "next_attempt_at", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tbl_publication_jobs_status"),
        "tbl_publication_jobs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tbl_publication_jobs_status"),
        table_name="tbl_publication_jobs",
    )
    op.drop_index("ix_publication_due", table_name="tbl_publication_jobs")
    op.drop_table("tbl_publication_jobs")
    op.drop_table("tbl_tracks")
    op.drop_table("tbl_settings")
    op.drop_table("tbl_plans")
    op.drop_table("tbl_owner_actions")
    op.drop_table("tbl_model_calls")
    op.drop_index(op.f("ix_tbl_inboxes_status"), table_name="tbl_inboxes")
    op.drop_table("tbl_inboxes")
    op.drop_table("tbl_import_sessions")
    op.drop_table("tbl_delivery_gates")
    op.drop_table("tbl_delete_confirmations")
    op.drop_table("tbl_daily_calls")
    op.drop_table("tbl_conversations")
    op.drop_index(
        "ix_conversation_history", table_name="tbl_conversation_pairs"
    )
    op.drop_table("tbl_conversation_pairs")
    op.drop_index(
        op.f("ix_tbl_chat_requests_status"), table_name="tbl_chat_requests"
    )
    op.drop_index("ix_chat_request_due", table_name="tbl_chat_requests")
    op.drop_index("ix_chat_rate", table_name="tbl_chat_requests")
    op.drop_table("tbl_chat_requests")
    op.drop_index("ix_channel_context", table_name="tbl_channel_posts")
    op.drop_table("tbl_channel_posts")
    op.drop_table("tbl_channel_imports")
    op.drop_table("tbl_channel_coverages")
