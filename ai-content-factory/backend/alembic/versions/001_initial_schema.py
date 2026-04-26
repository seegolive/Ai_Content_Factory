"""001 initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("google_id", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column(
            "plan",
            sa.Enum("free", "pro", "agency", name="user_plan"),
            nullable=False,
            server_default="free",
        ),
        sa.Column("credits_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_id", "users", ["google_id"])

    op.create_table(
        "youtube_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.String(255), nullable=False),
        sa.Column("channel_name", sa.String(255), nullable=True),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_dna", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_youtube_accounts_channel_id", "youtube_accounts", ["channel_id"])

    op.create_table(
        "videos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("youtube_account_id", UUID(as_uuid=True), sa.ForeignKey("youtube_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("original_url", sa.Text, nullable=True),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("file_size_mb", sa.Float, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column(
            "status",
            sa.Enum("queued", "processing", "review", "done", "error", name="video_status"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("checkpoint", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "copyright_status",
            sa.Enum("unchecked", "clean", "flagged", name="copyright_status"),
            nullable=False,
            server_default="unchecked",
        ),
        sa.Column("transcript", sa.Text, nullable=True),
        sa.Column("transcript_segments", JSONB, nullable=False, server_default="[]"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_videos_user_status", "videos", ["user_id", "status"])
    op.create_index("ix_videos_created_at", "videos", ["created_at"])

    op.create_table(
        "clips",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", UUID(as_uuid=True), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("start_time", sa.Float, nullable=False),
        sa.Column("end_time", sa.Float, nullable=False),
        sa.Column("duration", sa.Float, nullable=True),
        sa.Column("viral_score", sa.Integer, nullable=True),
        sa.Column("hook_text", sa.Text, nullable=True),
        sa.Column("hashtags", JSONB, nullable=False, server_default="[]"),
        sa.Column("thumbnail_path", sa.Text, nullable=True),
        sa.Column("clip_path", sa.Text, nullable=True),
        sa.Column(
            "format",
            sa.Enum("horizontal", "vertical", "square", name="clip_format"),
            nullable=False,
            server_default="vertical",
        ),
        sa.Column(
            "qc_status",
            sa.Enum("pending", "passed", "failed", "manual_review", name="qc_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("qc_issues", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "review_status",
            sa.Enum("pending", "approved", "rejected", name="review_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("platform_status", JSONB, nullable=False, server_default="{}"),
        sa.Column("speaker_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_clips_video_review", "clips", ["video_id", "review_status"])
    op.create_index("ix_clips_viral_score", "clips", ["viral_score"])

    op.create_table(
        "brand_kits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("primary_color", sa.String(7), nullable=True),
        sa.Column("accent_color", sa.String(7), nullable=True),
        sa.Column("logo_path", sa.Text, nullable=True),
        sa.Column("font_primary", sa.String(100), nullable=True),
        sa.Column("sdxl_style_prompt", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_brand_kits_user_id", "brand_kits", ["user_id"])


def downgrade() -> None:
    op.drop_table("brand_kits")
    op.drop_table("clips")
    op.drop_table("videos")
    op.drop_table("youtube_accounts")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS user_plan")
    op.execute("DROP TYPE IF EXISTS video_status")
    op.execute("DROP TYPE IF EXISTS copyright_status")
    op.execute("DROP TYPE IF EXISTS clip_format")
    op.execute("DROP TYPE IF EXISTS qc_status")
    op.execute("DROP TYPE IF EXISTS review_status")
