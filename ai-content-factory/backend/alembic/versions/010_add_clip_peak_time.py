"""add peak_time to clips

Revision ID: 010_add_clip_peak_time
Revises: 009_add_clips_publish_settings
Create Date: 2026-09-02
"""
from alembic import op
import sqlalchemy as sa

revision = "010_add_clip_peak_time"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clips", sa.Column("peak_time", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("clips", "peak_time")
