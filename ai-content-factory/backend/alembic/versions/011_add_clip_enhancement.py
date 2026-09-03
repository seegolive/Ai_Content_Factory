"""add enhancement columns to clips

Revision ID: 011_add_clip_enhancement
Revises: 010_add_clip_peak_time
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

revision = "011_add_clip_enhancement"
down_revision = "010_add_clip_peak_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clips", sa.Column("enhanced_path", sa.Text(), nullable=True))
    op.add_column("clips", sa.Column("enhanced_status", sa.String(20), nullable=True))
    op.add_column("clips", sa.Column("enhanced_progress", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("clips", sa.Column("enhanced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("clips", "enhanced_at")
    op.drop_column("clips", "enhanced_progress")
    op.drop_column("clips", "enhanced_status")
    op.drop_column("clips", "enhanced_path")
