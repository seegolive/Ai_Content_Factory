"""002 analytics schema

Revision ID: 002
Revises: 001
Create Date: 2026-04-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── video_analytics ──────────────────────────────────────────────────────
    op.create_table(
        "video_analytics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "video_id",
            UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("youtube_video_id", sa.String(50), nullable=False),
        sa.Column("channel_id", sa.String(255), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("views", sa.Integer, nullable=False, server_default="0"),
        sa.Column("likes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("comments", sa.Integer, nullable=False, server_default="0"),
        sa.Column("shares", sa.Integer, nullable=False, server_default="0"),
        sa.Column("watch_time_minutes", sa.Float, nullable=False, server_default="0"),
        sa.Column("avg_view_duration_seconds", sa.Float, nullable=True),
        sa.Column("avg_view_percentage", sa.Float, nullable=True),
        sa.Column("impressions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("impression_ctr", sa.Float, nullable=True),
        sa.Column("subscribers_gained", sa.Integer, nullable=False, server_default="0"),
        sa.Column("subscribers_lost", sa.Integer, nullable=False, server_default="0"),
        sa.Column("revenue_usd", sa.Float, nullable=True),
        sa.Column("traffic_sources", JSONB, nullable=False, server_default="{}"),
        sa.Column("device_types", JSONB, nullable=False, server_default="{}"),
        sa.Column("top_geographies", JSONB, nullable=False, server_default="[]"),
        sa.Column("pulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("video_id", "snapshot_date", name="uq_video_analytics_video_date"),
    )
    op.create_index("ix_video_analytics_channel_date", "video_analytics", ["channel_id", "snapshot_date"])
    op.create_index("ix_video_analytics_youtube_id", "video_analytics", ["youtube_video_id"])

    # ── video_retention_curves ───────────────────────────────────────────────
    op.create_table(
        "video_retention_curves",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "video_id",
            UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("youtube_video_id", sa.String(50), nullable=False),
        sa.Column("data_points", JSONB, nullable=False, server_default="[]"),
        sa.Column("peak_moments", JSONB, nullable=False, server_default="[]"),
        sa.Column("drop_off_points", JSONB, nullable=False, server_default="[]"),
        sa.Column("pulled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("video_id", name="uq_video_retention_video"),
    )
    op.create_index("ix_video_retention_youtube_id", "video_retention_curves", ["youtube_video_id"])

    # ── channel_analytics_daily ──────────────────────────────────────────────
    op.create_table(
        "channel_analytics_daily",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "youtube_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("youtube_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_id", sa.String(255), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("total_views", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_watch_time_minutes", sa.Float, nullable=False, server_default="0"),
        sa.Column("subscribers_net", sa.Integer, nullable=False, server_default="0"),
        sa.Column("revenue_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("top_videos", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("channel_id", "date", name="uq_channel_daily_channel_date"),
    )
    op.create_index("ix_channel_daily_channel_date_desc", "channel_analytics_daily", ["channel_id", "date"])

    # ── content_dna_models ───────────────────────────────────────────────────
    op.create_table(
        "content_dna_models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "youtube_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("youtube_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_id", sa.String(255), unique=True, nullable=False),
        sa.Column("niche", sa.String(100), nullable=True),
        sa.Column("sub_niches", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "viral_score_weights",
            JSONB,
            nullable=False,
            server_default='{"emotional_impact":0.25,"hook_strength":0.25,"info_density":0.20,"relatability":0.20,"cta_potential":0.10}',
        ),
        sa.Column("top_performing_patterns", JSONB, nullable=False, server_default="{}"),
        sa.Column("game_performance", JSONB, nullable=False, server_default="{}"),
        sa.Column("underperforming_patterns", JSONB, nullable=False, server_default="{}"),
        sa.Column("confidence_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("videos_analyzed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_content_dna_channel_id", "content_dna_models", ["channel_id"])

    # ── weekly_insight_reports ───────────────────────────────────────────────
    op.create_table(
        "weekly_insight_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "youtube_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("youtube_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_id", sa.String(255), nullable=False),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("week_end", sa.Date, nullable=False),
        sa.Column("summary_text", sa.Text, nullable=True),
        sa.Column("key_wins", JSONB, nullable=False, server_default="[]"),
        sa.Column("key_issues", JSONB, nullable=False, server_default="[]"),
        sa.Column("recommendations", JSONB, nullable=False, server_default="[]"),
        sa.Column("top_clip_type", sa.String(100), nullable=True),
        sa.Column("views_change_pct", sa.Float, nullable=True),
        sa.Column("subscribers_change", sa.Integer, nullable=True),
        sa.Column("estimated_viral_potential", JSONB, nullable=False, server_default="{}"),
        sa.Column("raw_data_snapshot", JSONB, nullable=False, server_default="{}"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("channel_id", "week_start", name="uq_weekly_report_channel_week"),
    )
    op.create_index("ix_weekly_reports_channel_id", "weekly_insight_reports", ["channel_id"])


def downgrade() -> None:
    op.drop_table("weekly_insight_reports")
    op.drop_table("content_dna_models")
    op.drop_table("channel_analytics_daily")
    op.drop_table("video_retention_curves")
    op.drop_table("video_analytics")
