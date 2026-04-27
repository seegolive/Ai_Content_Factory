"""006 make video_retention_curves.video_id nullable, add unique on youtube_video_id

Revision ID: 006
Revises: 005
Create Date: 2026-04-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old unique constraint and FK
    op.drop_constraint("uq_video_retention_video", "video_retention_curves", type_="unique")
    op.drop_constraint("video_retention_curves_video_id_fkey", "video_retention_curves", type_="foreignkey")

    # Make video_id nullable
    op.alter_column("video_retention_curves", "video_id", nullable=True)

    # Re-add FK with SET NULL on delete
    op.create_foreign_key(
        "video_retention_curves_video_id_fkey",
        "video_retention_curves", "videos",
        ["video_id"], ["id"],
        ondelete="SET NULL",
    )

    # New unique on youtube_video_id
    op.create_unique_constraint(
        "uq_video_retention_youtube_id",
        "video_retention_curves",
        ["youtube_video_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_video_retention_youtube_id", "video_retention_curves", type_="unique")
    op.drop_constraint("video_retention_curves_video_id_fkey", "video_retention_curves", type_="foreignkey")
    op.alter_column("video_retention_curves", "video_id", nullable=False)
    op.create_foreign_key(
        "video_retention_curves_video_id_fkey",
        "video_retention_curves", "videos",
        ["video_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_video_retention_video",
        "video_retention_curves",
        ["video_id"],
    )
