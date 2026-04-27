"""007 channel crop config

Revision ID: 007
Revises: 006
Create Date: 2026-04-26 00:00:01.000000

Creates:
  - channel_crop_configs
  - game_crop_profiles
  - Enums: vertical_crop_mode, facecam_position_type, crop_anchor_type
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, ENUM as pgENUM

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'vertical_crop_mode') THEN
                CREATE TYPE vertical_crop_mode AS ENUM (
                    'blur_pillarbox', 'smart_offset', 'dual_zone', 'passthrough'
                );
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'facecam_position_type') THEN
                CREATE TYPE facecam_position_type AS ENUM (
                    'top_left', 'top_right', 'bottom_left', 'bottom_right',
                    'top_center_full', 'none'
                );
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'crop_anchor_type') THEN
                CREATE TYPE crop_anchor_type AS ENUM ('left', 'center', 'right');
            END IF;
        END$$;
    """)

    op.create_table(
        "channel_crop_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "youtube_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("youtube_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_id", sa.String(255), nullable=False, unique=True),
        sa.Column("obs_canvas_width", sa.Integer, nullable=False, server_default="2560"),
        sa.Column("obs_canvas_height", sa.Integer, nullable=False, server_default="1440"),
        sa.Column("obs_fps", sa.Integer, nullable=False, server_default="60"),
        sa.Column(
            "default_vertical_crop_mode",
            pgENUM(
                "blur_pillarbox", "smart_offset", "dual_zone", "passthrough",
                name="vertical_crop_mode", create_type=False
            ),
            nullable=False, server_default="blur_pillarbox",
        ),
        sa.Column(
            "default_facecam_position",
            pgENUM(
                "top_left", "top_right", "bottom_left", "bottom_right",
                "top_center_full", "none",
                name="facecam_position_type", create_type=False
            ),
            nullable=False, server_default="top_left",
        ),
        sa.Column("default_crop_x_offset", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "default_crop_anchor",
            pgENUM("left", "center", "right", name="crop_anchor_type", create_type=False),
            nullable=False, server_default="left",
        ),
        sa.Column("default_dual_zone_split_ratio", sa.Float, nullable=False, server_default="0.38"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_channel_crop_configs_youtube_account_id", "channel_crop_configs", ["youtube_account_id"])

    op.create_table(
        "game_crop_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "channel_crop_config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("channel_crop_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_id", sa.String(255), nullable=False),
        sa.Column("game_name", sa.String(255), nullable=False),
        sa.Column("game_name_aliases", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "vertical_crop_mode",
            pgENUM(
                "blur_pillarbox", "smart_offset", "dual_zone", "passthrough",
                name="vertical_crop_mode", create_type=False
            ),
            nullable=False, server_default="blur_pillarbox",
        ),
        sa.Column("facecam_position", sa.String(50), nullable=True),
        sa.Column("facecam_x", sa.Integer, nullable=True),
        sa.Column("facecam_y", sa.Integer, nullable=True),
        sa.Column("facecam_width", sa.Integer, nullable=True),
        sa.Column("facecam_height", sa.Integer, nullable=True),
        sa.Column("crop_x_offset", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "crop_anchor",
            pgENUM("left", "center", "right", name="crop_anchor_type", create_type=False),
            nullable=False, server_default="left",
        ),
        sa.Column("dual_zone_split_ratio", sa.Float, nullable=False, server_default="0.38"),
        sa.Column("gameplay_crop_center_x", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_game_crop_profiles_channel_id", "game_crop_profiles", ["channel_id"])
    op.create_index(
        "ix_game_crop_profiles_config_id", "game_crop_profiles", ["channel_crop_config_id"]
    )
    op.create_unique_constraint(
        "uq_game_profile_channel_game", "game_crop_profiles", ["channel_id", "game_name"]
    )


def downgrade() -> None:
    op.drop_table("game_crop_profiles")
    op.drop_table("channel_crop_configs")
    op.execute("DROP TYPE IF EXISTS crop_anchor_type")
    op.execute("DROP TYPE IF EXISTS facecam_position_type")
    op.execute("DROP TYPE IF EXISTS vertical_crop_mode")
