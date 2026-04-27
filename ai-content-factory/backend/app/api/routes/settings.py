"""Settings API routes — channel crop config, facecam detect, preview crop."""
import base64
import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.models.channel_config import ChannelCropConfig, GameCropProfile, seed_default_game_profiles
from app.models.user import User
from app.services.facecam_detector import FacecamDetector

router = APIRouter(prefix="/settings", tags=["settings"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CropConfigOut(BaseModel):
    id: str
    channel_id: str
    obs_canvas_width: int
    obs_canvas_height: int
    obs_fps: int
    default_vertical_crop_mode: str
    default_facecam_position: str
    default_crop_x_offset: int
    default_crop_anchor: str
    default_dual_zone_split_ratio: float
    game_profiles: list[dict]


class CropConfigUpdate(BaseModel):
    default_vertical_crop_mode: Optional[str] = None
    default_facecam_position: Optional[str] = None
    default_crop_x_offset: Optional[int] = None
    default_crop_anchor: Optional[str] = None
    default_dual_zone_split_ratio: Optional[float] = None
    obs_canvas_width: Optional[int] = None
    obs_canvas_height: Optional[int] = None
    obs_fps: Optional[int] = None


class DetectFacecamRequest(BaseModel):
    video_id: str


class PreviewCropRequest(BaseModel):
    video_id: str
    vertical_crop_mode: str = "blur_pillarbox"
    crop_x_offset: int = 0
    crop_anchor: str = "left"
    timestamp_seconds: float = 5.0


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_create_config(
    channel_id: str, youtube_account_id: uuid.UUID, db: AsyncSession
) -> ChannelCropConfig:
    """Load or create ChannelCropConfig for the given channel."""
    result = await db.execute(
        select(ChannelCropConfig).where(ChannelCropConfig.channel_id == channel_id)
    )
    config = result.scalars().first()
    if config:
        return config

    config = ChannelCropConfig(
        youtube_account_id=youtube_account_id,
        channel_id=channel_id,
    )
    db.add(config)
    await db.flush()  # get config.id before seeding profiles

    profiles = seed_default_game_profiles(config)
    for p in profiles:
        db.add(p)

    await db.commit()
    await db.refresh(config)
    logger.info(f"[Settings] Created default crop config for channel {channel_id}")
    return config


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/channel/{channel_id}/crop-config", response_model=CropConfigOut)
async def get_crop_config(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CropConfigOut:
    """Get channel vertical crop configuration."""
    # Verify user owns this channel
    yt_account = next(
        (a for a in current_user.youtube_accounts if a.channel_id == channel_id), None
    )
    if not yt_account:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Channel not found")

    config = await _get_or_create_config(channel_id, yt_account.id, db)
    profiles_result = await db.execute(
        select(GameCropProfile).where(GameCropProfile.channel_crop_config_id == config.id)
    )
    profiles = profiles_result.scalars().all()

    return CropConfigOut(
        id=str(config.id),
        channel_id=config.channel_id,
        obs_canvas_width=config.obs_canvas_width,
        obs_canvas_height=config.obs_canvas_height,
        obs_fps=config.obs_fps,
        default_vertical_crop_mode=config.default_vertical_crop_mode,
        default_facecam_position=config.default_facecam_position,
        default_crop_x_offset=config.default_crop_x_offset,
        default_crop_anchor=config.default_crop_anchor,
        default_dual_zone_split_ratio=config.default_dual_zone_split_ratio,
        game_profiles=[
            {
                "id": str(p.id),
                "game_name": p.game_name,
                "aliases": p.game_name_aliases,
                "vertical_crop_mode": p.vertical_crop_mode,
                "facecam_position": p.facecam_position,
                "crop_x_offset": p.crop_x_offset,
                "crop_anchor": p.crop_anchor,
                "dual_zone_split_ratio": p.dual_zone_split_ratio,
                "is_active": p.is_active,
            }
            for p in profiles
        ],
    )


@router.put("/channel/{channel_id}/crop-config", response_model=CropConfigOut)
async def update_crop_config(
    channel_id: str,
    body: CropConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CropConfigOut:
    """Update channel default crop configuration."""
    yt_account = next(
        (a for a in current_user.youtube_accounts if a.channel_id == channel_id), None
    )
    if not yt_account:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Channel not found")

    config = await _get_or_create_config(channel_id, yt_account.id, db)

    update_data = body.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)
    logger.info(f"[Settings] Updated crop config for channel {channel_id}: {update_data}")
    return await get_crop_config(channel_id, current_user, db)


@router.post("/channel/{channel_id}/detect-facecam")
async def detect_facecam(
    channel_id: str,
    body: DetectFacecamRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Run facecam auto-detection on a video.
    Returns detected region + suggested crop config for user to confirm.
    """
    yt_account = next(
        (a for a in current_user.youtube_accounts if a.channel_id == channel_id), None
    )
    if not yt_account:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Channel not found")

    # Load video file path
    from app.models.video import Video
    result = await db.execute(
        select(Video).where(
            Video.id == uuid.UUID(body.video_id),
            Video.user_id == current_user.id,
        )
    )
    video = result.scalars().first()
    if not video or not video.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    detector = FacecamDetector()
    region = detector.detect_facecam_region(video.file_path)

    if not region:
        return {
            "detected": False,
            "region": None,
            "suggested_config": None,
            "message": "Facecam tidak terdeteksi otomatis — silakan atur manual",
        }

    suggested = detector.suggest_crop_config(region)
    return {
        "detected": True,
        "region": {
            "x": region.x, "y": region.y,
            "width": region.width, "height": region.height,
            "position": region.position,
        },
        "suggested_config": suggested,
        "message": f"Facecam terdeteksi di {region.position}",
    }


@router.post("/channel/{channel_id}/preview-crop")
async def preview_crop(
    channel_id: str,
    body: PreviewCropRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate a preview frame showing how the crop will look.
    Returns base64-encoded JPEG image.
    """
    yt_account = next(
        (a for a in current_user.youtube_accounts if a.channel_id == channel_id), None
    )
    if not yt_account:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Channel not found")

    from app.models.video import Video
    result = await db.execute(
        select(Video).where(
            Video.id == uuid.UUID(body.video_id),
            Video.user_id == current_user.id,
        )
    )
    video = result.scalars().first()
    if not video or not video.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    import asyncio
    import tempfile

    # Extract single frame at timestamp
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        frame_path = f.name

    try:
        # Get frame from source video
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-ss", str(body.timestamp_seconds),
            "-i", video.file_path,
            "-vframes", "1", "-q:v", "2", frame_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=30)

        # Apply crop filter to generate 9:16 preview
        source_w = 2560  # default Seego GG
        source_h = 1440
        crop_h = source_h
        crop_w = int(source_h * 9 / 16)  # 810

        if body.vertical_crop_mode == "smart_offset":
            anchor = body.crop_anchor
            x_offset = body.crop_x_offset
            x = max(0, x_offset) if anchor == "left" else max(0, source_w - crop_w - x_offset)
            vf = f"crop={crop_w}:{crop_h}:{x}:0,scale=270:480"
        else:
            # blur_pillarbox preview
            vf = (
                "split[o][c];[c]scale=270:480:force_original_aspect_ratio=increase,"
                "crop=270:480,boxblur=20:3[b];[o]scale=270:-2[s];[b][s]overlay=(W-w)/2:(H-h)/2"
            )

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f2:
            preview_path = f2.name

        proc2 = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", frame_path,
            "-vf", vf, "-vframes", "1", "-q:v", "3", preview_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc2.communicate(), timeout=30)

        with open(preview_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        return {
            "preview_base64": f"data:image/jpeg;base64,{img_b64}",
            "crop_mode": body.vertical_crop_mode,
            "timestamp": body.timestamp_seconds,
        }
    except Exception as e:
        logger.error(f"[Settings] Preview crop failed: {e}")
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")
    finally:
        import os as _os
        for p in [frame_path]:
            try:
                _os.unlink(p)
            except Exception:
                pass
