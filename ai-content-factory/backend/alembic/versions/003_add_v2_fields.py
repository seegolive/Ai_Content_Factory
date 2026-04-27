"""003 add v2 fields — moment_type, ai_provider_used, multi-format paths

Revision ID: 003
Revises: 002
Create Date: 2026-04-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── clips table ──────────────────────────────────────────────────────────
    op.add_column("clips", sa.Column("moment_type", sa.String(50), nullable=True))
    op.add_column("clips", sa.Column("clip_path_horizontal", sa.Text, nullable=True))
    op.add_column("clips", sa.Column("clip_path_vertical", sa.Text, nullable=True))
    op.add_column("clips", sa.Column("clip_path_square", sa.Text, nullable=True))
    op.add_column(
        "clips",
        sa.Column("format_generated", JSONB, nullable=False, server_default="{}"),
    )
    op.add_column("clips", sa.Column("ai_provider_used", sa.String(100), nullable=True))

    # ── videos table ─────────────────────────────────────────────────────────
    op.add_column("videos", sa.Column("ai_provider_used", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "ai_provider_used")

    op.drop_column("clips", "ai_provider_used")
    op.drop_column("clips", "format_generated")
    op.drop_column("clips", "clip_path_square")
    op.drop_column("clips", "clip_path_vertical")
    op.drop_column("clips", "clip_path_horizontal")
    op.drop_column("clips", "moment_type")
