"""002 make video_analytics.video_id nullable for YouTube-only videos

Revision ID: 002
Revises: 001
Create Date: 2026-04-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old unique constraint based on (video_id, snapshot_date)
    op.drop_constraint("uq_video_analytics_video_date", "video_analytics", type_="unique")

    # Drop the FK so we can make the column nullable
    op.drop_constraint("video_analytics_video_id_fkey", "video_analytics", type_="foreignkey")

    # Make video_id nullable
    op.alter_column("video_analytics", "video_id", nullable=True)

    # Re-add FK with nullable semantics (ON DELETE SET NULL)
    op.create_foreign_key(
        "video_analytics_video_id_fkey",
        "video_analytics", "videos",
        ["video_id"], ["id"],
        ondelete="SET NULL",
    )

    # New unique constraint: (youtube_video_id, snapshot_date, channel_id)
    op.create_unique_constraint(
        "uq_video_analytics_yt_date",
        "video_analytics",
        ["youtube_video_id", "snapshot_date", "channel_id"],
    )

    # Add channel_videos_count to youtube_accounts for UI display
    op.add_column(
        "youtube_accounts",
        sa.Column("channel_videos_count", sa.Integer, nullable=True),
    )
    op.add_column(
        "youtube_accounts",
        sa.Column("channel_total_views", sa.BigInteger, nullable=True),
    )
    op.add_column(
        "youtube_accounts",
        sa.Column("channel_subscribers", sa.BigInteger, nullable=True),
    )
    op.add_column(
        "youtube_accounts",
        sa.Column("last_analytics_sync", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("youtube_accounts", "last_analytics_sync")
    op.drop_column("youtube_accounts", "channel_subscribers")
    op.drop_column("youtube_accounts", "channel_total_views")
    op.drop_column("youtube_accounts", "channel_videos_count")
    op.drop_constraint("uq_video_analytics_yt_date", "video_analytics", type_="unique")
    op.drop_constraint("video_analytics_video_id_fkey", "video_analytics", type_="foreignkey")
    op.alter_column("video_analytics", "video_id", nullable=False)
    op.create_foreign_key(
        "video_analytics_video_id_fkey",
        "video_analytics", "videos",
        ["video_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_video_analytics_video_date",
        "video_analytics",
        ["video_id", "snapshot_date"],
    )
