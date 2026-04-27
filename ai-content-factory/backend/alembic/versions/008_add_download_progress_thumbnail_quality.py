"""Add download_progress, thumbnail_url, quality_preference to videos

Revision ID: 002
Revises: 001
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("videos", sa.Column("thumbnail_url", sa.Text(), nullable=True))
    op.add_column("videos", sa.Column("download_progress", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("videos", sa.Column("quality_preference", sa.String(20), nullable=True, server_default="1440p"))


def downgrade():
    op.drop_column("videos", "quality_preference")
    op.drop_column("videos", "download_progress")
    op.drop_column("videos", "thumbnail_url")
