"""Clips review and management routes."""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.security import bearer_scheme, create_access_token, verify_token
from app.models.clip import Clip
from app.models.user import User
from app.models.video import Video
from app.schemas.clip import (
    ClipBulkReviewRequest,
    ClipOut,
    ClipPublishRequest,
    ClipReviewRequest,
    ClipUpdateRequest,
)

router = APIRouter()


async def _get_clip_or_404(
    clip_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Clip:
    result = await db.execute(
        select(Clip).where(Clip.id == clip_id, Clip.user_id == user_id)
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return clip


@router.get("/videos/{video_id}/clips", response_model=List[ClipOut])
async def list_clips(
    video_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    qc_status: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    viral_score_min: Optional[int] = Query(None, ge=0, le=100),
    sort: str = Query("viral_score", regex="^(viral_score|created_at)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List clips for a video."""
    # Verify video belongs to user
    video_result = await db.execute(
        select(Video.id).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    if not video_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    query = select(Clip).where(Clip.video_id == video_id)
    if qc_status:
        query = query.where(Clip.qc_status == qc_status)
    if review_status:
        query = query.where(Clip.review_status == review_status)
    if viral_score_min is not None:
        query = query.where(Clip.viral_score >= viral_score_min)

    if sort == "viral_score":
        query = query.order_by(Clip.viral_score.desc().nulls_last())
    else:
        query = query.order_by(Clip.created_at.desc())

    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    clips = result.scalars().all()
    return [ClipOut.model_validate(c) for c in clips]


@router.patch("/clips/{clip_id}/review", response_model=ClipOut)
async def review_clip(
    clip_id: uuid.UUID,
    body: ClipReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a single clip."""
    clip = await _get_clip_or_404(clip_id, current_user.id, db)
    clip.review_status = "approved" if body.action == "approve" else "rejected"
    clip.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return ClipOut.model_validate(clip)


@router.post("/clips/bulk-review")
async def bulk_review(
    body: ClipBulkReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk approve or reject clips."""
    new_status = "approved" if body.action == "approve" else "rejected"
    now = datetime.now(timezone.utc)

    await db.execute(
        update(Clip)
        .where(Clip.id.in_(body.clip_ids), Clip.user_id == current_user.id)
        .values(review_status=new_status, reviewed_at=now)
    )
    await db.commit()
    # Use rowcount for accurate count of actually-updated rows
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count(Clip.id)).where(
            Clip.id.in_(body.clip_ids),
            Clip.user_id == current_user.id,
            Clip.review_status == new_status,
        )
    )
    updated_count = count_result.scalar_one()
    return {"updated": updated_count, "review_status": new_status}


@router.patch("/clips/{clip_id}", response_model=ClipOut)
async def update_clip(
    clip_id: uuid.UUID,
    body: ClipUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit clip metadata before publishing."""
    clip = await _get_clip_or_404(clip_id, current_user.id, db)
    if body.title is not None:
        clip.title = body.title
    if body.description is not None:
        clip.description = body.description
    if body.hashtags is not None:
        clip.hashtags = body.hashtags
    await db.commit()
    return ClipOut.model_validate(clip)


@router.post("/clips/{clip_id}/publish", status_code=status.HTTP_202_ACCEPTED)
async def publish_clip(
    clip_id: uuid.UUID,
    body: ClipPublishRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger distribution to selected platforms."""
    clip = await _get_clip_or_404(clip_id, current_user.id, db)
    if clip.review_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clip must be approved before publishing",
        )

    # Verify YouTube account ownership before dispatching
    if body.youtube_account_id:
        from app.models.video import YoutubeAccount
        yt_result = await db.execute(
            select(YoutubeAccount).where(
                YoutubeAccount.id == body.youtube_account_id,
                YoutubeAccount.user_id == current_user.id,
            )
        )
        if not yt_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="YouTube account not found")

    try:
        from app.workers.tasks.distribute import distribute_clip
        task = distribute_clip.delay(
            str(clip_id),
            body.platforms,
            str(body.youtube_account_id) if body.youtube_account_id else None,
        )
        return {"publish_job_id": task.id, "platforms": body.platforms}
    except Exception as e:
        logger.error(f"Failed to queue distribution for clip {clip_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to queue publish"
        )


@router.get("/clips/{clip_id}/stream-token")
async def get_stream_token(
    clip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Issue a short-lived (1h) signed token for use as ?token= in the stream URL.

    This allows the browser's native <video> element to stream authenticated
    clip files without needing to set an Authorization header.
    """
    clip = await _get_clip_or_404(clip_id, current_user.id, db)
    if not clip.clip_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip file not found")

    token = create_access_token(
        {"sub": str(current_user.id), "type": "stream", "clip_id": str(clip_id)},
        expires_delta=timedelta(hours=1),
    )
    return {"token": token, "expires_in": 3600}


@router.get("/clips/{clip_id}/stream")
async def stream_clip(
    clip_id: uuid.UUID,
    request: Request,
    token: Optional[str] = Query(None, description="Short-lived stream token from /stream-token"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Stream clip file with Range support for video player seek.

    Authentication: accepts either:
    - ?token=<stream_token>  (from /stream-token endpoint, for <video> tags)
    - Authorization: Bearer <jwt>  (standard API auth)
    """
    # Resolve token from query param or Authorization header
    raw_token = token or (credentials.credentials if credentials else None)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = verify_token(raw_token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Verify clip ownership
    result = await db.execute(
        select(Clip).where(Clip.id == clip_id)
    )
    clip = result.scalar_one_or_none()
    if not clip or str(clip.user_id) != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")

    if not clip.clip_path or not os.path.exists(clip.clip_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip file not found")

    file_size = os.path.getsize(clip.clip_path)

    # Parse Range header for seek support
    range_header = request.headers.get("Range")
    start, end = 0, file_size - 1
    http_status = 200

    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else file_size - 1
            end = min(end, file_size - 1)
            http_status = 206

    content_length = end - start + 1

    def iterfile(path: str, byte_start: int, byte_end: int):
        with open(path, "rb") as f:
            f.seek(byte_start)
            remaining = byte_end - byte_start + 1
            chunk_size = 65536
            while remaining > 0:
                data = f.read(min(chunk_size, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iterfile(clip.clip_path, start, end),
        status_code=http_status,
        media_type="video/mp4",
        headers={
            "Content-Length": str(content_length),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
        },
    )
