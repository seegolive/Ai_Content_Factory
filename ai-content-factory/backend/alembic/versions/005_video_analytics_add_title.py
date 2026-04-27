"""005 add video_title to video_analytics

Revision ID: 005
Revises: 004
Create Date: 2026-04-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_analytics",
        sa.Column("video_title", sa.String(500), nullable=True),
    )
    op.add_column(
        "video_analytics",
        sa.Column("video_thumbnail_url", sa.Text, nullable=True),
    )
    op.add_column(
        "video_analytics",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("video_analytics", "published_at")
    op.drop_column("video_analytics", "video_thumbnail_url")
    op.drop_column("video_analytics", "video_title")
