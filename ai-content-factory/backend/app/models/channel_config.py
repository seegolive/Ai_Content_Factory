"""ChannelCropConfig and GameCropProfile models for facecam-aware vertical crop."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

# Enums shared with pydantic schemas
CROP_MODE_ENUM = Enum(
    "blur_pillarbox",
    "smart_offset",
    "dual_zone",
    "passthrough",
    "center_crop",
    "blur_letterbox",
    name="vertical_crop_mode",
)

FACECAM_POSITION_ENUM = Enum(
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
    "top_center_full",
    "none",
    name="facecam_position_type",
)

CROP_ANCHOR_ENUM = Enum("left", "center", "right", name="crop_anchor_type")


class ChannelCropConfig(Base):
    """Default vertical crop settings per YouTube channel."""

    __tablename__ = "channel_crop_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    youtube_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("youtube_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # OBS canvas specs — Seego GG: 2560x1440 @60fps
    obs_canvas_width: Mapped[int] = mapped_column(Integer, default=2560, nullable=False)
    obs_canvas_height: Mapped[int] = mapped_column(
        Integer, default=1440, nullable=False
    )
    obs_fps: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # Default crop mode (used for unknown games)
    default_vertical_crop_mode: Mapped[str] = mapped_column(
        CROP_MODE_ENUM, default="blur_pillarbox", nullable=False
    )

    # Default facecam position for smart_offset mode
    default_facecam_position: Mapped[str] = mapped_column(
        FACECAM_POSITION_ENUM, default="top_left", nullable=False
    )

    # Default smart_offset params
    default_crop_x_offset: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    default_crop_anchor: Mapped[str] = mapped_column(
        CROP_ANCHOR_ENUM, default="left", nullable=False
    )

    # Default dual_zone params
    default_dual_zone_split_ratio: Mapped[float] = mapped_column(
        Float, default=0.38, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    game_profiles: Mapped[list["GameCropProfile"]] = relationship(
        "GameCropProfile",
        back_populates="channel_config",
        cascade="all, delete-orphan",
    )


class GameCropProfile(Base):
    """Per-game crop settings that override channel defaults."""

    __tablename__ = "game_crop_profiles"

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "game_name", name="uq_game_profile_channel_game"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_crop_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channel_crop_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Game identification
    game_name: Mapped[str] = mapped_column(String(255), nullable=False)
    game_name_aliases: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Crop mode override
    vertical_crop_mode: Mapped[str] = mapped_column(
        CROP_MODE_ENUM, default="blur_pillarbox", nullable=False
    )

    # Facecam config
    facecam_position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    facecam_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    facecam_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    facecam_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    facecam_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Smart offset params
    crop_x_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    crop_anchor: Mapped[str] = mapped_column(
        CROP_ANCHOR_ENUM, default="left", nullable=False
    )

    # Dual zone params
    dual_zone_split_ratio: Mapped[float] = mapped_column(
        Float, default=0.38, nullable=False
    )
    gameplay_crop_center_x: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship
    channel_config: Mapped["ChannelCropConfig"] = relationship(
        "ChannelCropConfig", back_populates="game_profiles"
    )


def seed_default_game_profiles(config: ChannelCropConfig) -> list[GameCropProfile]:
    """Return default game profiles for Seego GG (call once after creating ChannelCropConfig)."""
    channel_id = config.channel_id
    cfg_id = config.id
    return [
        GameCropProfile(
            channel_crop_config_id=cfg_id,
            channel_id=channel_id,
            game_name="Battlefield 6",
            game_name_aliases=["BF6", "Battlefield VI", "Battlefield"],
            vertical_crop_mode="smart_offset",
            facecam_position="top_left",
            facecam_x=0,
            facecam_y=0,
            facecam_width=320,
            facecam_height=270,
            crop_x_offset=0,
            crop_anchor="left",
        ),
        GameCropProfile(
            channel_crop_config_id=cfg_id,
            channel_id=channel_id,
            game_name="Valorant",
            game_name_aliases=["VALORANT", "Val"],
            vertical_crop_mode="dual_zone",
            facecam_position="top_center_full",
            facecam_x=0,
            facecam_y=0,
            facecam_width=2560,
            facecam_height=547,
            dual_zone_split_ratio=0.38,
            gameplay_crop_center_x=1280,
        ),
        GameCropProfile(
            channel_crop_config_id=cfg_id,
            channel_id=channel_id,
            game_name="Arc Raiders",
            game_name_aliases=["ArcRaiders"],
            vertical_crop_mode="smart_offset",
            facecam_position="top_left",
            crop_x_offset=0,
            crop_anchor="left",
        ),
        GameCropProfile(
            channel_crop_config_id=cfg_id,
            channel_id=channel_id,
            game_name="Kingdom Come Deliverance II",
            game_name_aliases=["KCD2", "Kingdom Come 2", "Kingdom Come Deliverance"],
            vertical_crop_mode="smart_offset",
            facecam_position="top_left",
            crop_x_offset=0,
            crop_anchor="left",
        ),
        GameCropProfile(
            channel_crop_config_id=cfg_id,
            channel_id=channel_id,
            game_name="_default",
            game_name_aliases=[],
            vertical_crop_mode="blur_pillarbox",
        ),
    ]
