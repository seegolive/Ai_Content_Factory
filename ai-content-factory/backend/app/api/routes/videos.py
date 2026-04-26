"""Video management API routes."""
import os
import shutil
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.config import settings
from app.models.clip import Clip
from app.models.user import User
from app.models.video import Video
from app.schemas.video import (
    VideoDetailOut,
    VideoFromUrlRequest,
    VideoOut,
    VideoStatusResponse,
    VideoUploadResponse,
)

router = APIRouter()

STAGE_PROGRESS = {
    None: 0,
    "input_validated": 10,
    "transcript_done": 35,
    "ai_done": 55,
    "qc_done": 70,
    "clips_done": 90,
    "review_ready": 100,
}

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def _get_progress(checkpoint: Optional[str]) -> int:
    return STAGE_PROGRESS.get(checkpoint, 0)


@router.post("/videos/upload", response_model=VideoUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a video file and start processing pipeline."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}",
        )

    # Save to local storage
    video_id = uuid.uuid4()
    storage_dir = os.path.join(settings.LOCAL_STORAGE_PATH, "videos")
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, f"{video_id}{ext}")

    size_bytes = 0
    with open(file_path, "wb") as f:
        chunk_size = 1024 * 1024  # 1MB chunks
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > settings.max_video_size_bytes:
                os.remove(file_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds {settings.MAX_VIDEO_SIZE_GB}GB limit",
                )
            f.write(chunk)

    size_mb = size_bytes / (1024 * 1024)

    video = Video(
        id=video_id,
        user_id=current_user.id,
        title=os.path.splitext(file.filename or str(video_id))[0],
        file_path=file_path,
        file_size_mb=size_mb,
        status="queued",
    )
    db.add(video)
    await db.commit()

    # Trigger pipeline
    try:
        from app.workers.tasks.pipeline import process_video_pipeline
        task = process_video_pipeline.delay(str(video_id))
        video.celery_task_id = task.id
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to queue pipeline for video {video_id}: {e}")

    return VideoUploadResponse(
        video_id=video_id,
        status="queued",
        message="Video uploaded and queued for processing",
    )


@router.post("/videos/from-url", response_model=VideoUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def video_from_url(
    body: VideoFromUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a video job from a YouTube URL."""
    video_id = uuid.uuid4()
    video = Video(
        id=video_id,
        user_id=current_user.id,
        youtube_account_id=body.youtube_account_id,
        original_url=body.youtube_url,
        title=body.youtube_url,
        status="queued",
    )
    db.add(video)
    await db.commit()

    try:
        from app.workers.tasks.pipeline import process_video_pipeline
        task = process_video_pipeline.delay(str(video_id))
        video.celery_task_id = task.id
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to queue pipeline for video {video_id}: {e}")

    return VideoUploadResponse(
        video_id=video_id,
        status="queued",
        message="YouTube URL queued for processing",
    )


@router.get("/videos", response_model=List[VideoOut])
async def list_videos(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all videos for current user with clip counts."""
    query = select(Video).where(Video.user_id == current_user.id)
    if status_filter:
        query = query.where(Video.status == status_filter)
    query = query.order_by(Video.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    videos = result.scalars().all()

    # Fetch clip counts
    video_ids = [v.id for v in videos]
    clips_count_map: dict = {}
    if video_ids:
        counts_result = await db.execute(
            select(Clip.video_id, func.count(Clip.id))
            .where(Clip.video_id.in_(video_ids))
            .group_by(Clip.video_id)
        )
        clips_count_map = {row[0]: row[1] for row in counts_result.all()}

    return [
        VideoOut(
            **{c.key: getattr(v, c.key) for c in Video.__table__.columns},
            clips_count=clips_count_map.get(v.id, 0),
        )
        for v in videos
    ]


@router.get("/videos/{video_id}", response_model=VideoDetailOut)
async def get_video(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get video detail."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    clips_result = await db.execute(
        select(func.count(Clip.id)).where(Clip.video_id == video_id)
    )
    clips_count = clips_result.scalar_one()

    return VideoDetailOut(
        **{c.key: getattr(video, c.key) for c in Video.__table__.columns},
        clips_count=clips_count,
    )


@router.get("/videos/{video_id}/status", response_model=VideoStatusResponse)
async def get_video_status(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight polling endpoint for real-time status."""
    result = await db.execute(
        select(Video.status, Video.checkpoint, Video.error_message).where(
            Video.id == video_id, Video.user_id == current_user.id
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    return VideoStatusResponse(
        video_id=video_id,
        status=row.status,
        checkpoint=row.checkpoint,
        progress_percent=_get_progress(row.checkpoint),
        current_stage=row.checkpoint,
        error_message=row.error_message,
    )


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete video and cancel Celery task if running."""
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    # Cancel Celery task
    if video.celery_task_id:
        try:
            from app.workers.celery_app import celery_app
            celery_app.control.revoke(video.celery_task_id, terminate=True)
        except Exception as e:
            logger.warning(f"Could not cancel Celery task {video.celery_task_id}: {e}")

    # Delete physical file
    if video.file_path and os.path.exists(video.file_path):
        try:
            os.remove(video.file_path)
        except Exception as e:
            logger.warning(f"Could not delete file {video.file_path}: {e}")

    await db.delete(video)
    await db.commit()
