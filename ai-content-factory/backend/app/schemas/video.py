"""Video Pydantic schemas."""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class VideoUploadResponse(BaseModel):
    video_id: uuid.UUID
    status: str
    message: str


class VideoFromUrlRequest(BaseModel):
    youtube_url: str
    youtube_account_id: Optional[uuid.UUID] = None
    quality_preference: Optional[str] = "1440p"  # "1080p" | "1440p" | "2160p" | "best"

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if not ("youtube.com/watch" in v or "youtu.be/" in v):
            raise ValueError("Must be a valid YouTube URL")
        return v

    @field_validator("quality_preference")
    @classmethod
    def validate_quality(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"1080p", "1440p", "2160p", "best"}
        if v and v not in allowed:
            raise ValueError(f"quality_preference must be one of {allowed}")
        return v


class VideoPreviewResponse(BaseModel):
    title: str
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    uploader: Optional[str] = None
    view_count: Optional[int] = None
    upload_date: Optional[str] = None
    available_qualities: List[str] = []


class VideoStatusResponse(BaseModel):
    video_id: uuid.UUID
    status: str
    checkpoint: Optional[str] = None
    progress_percent: int
    download_progress: Optional[int] = None
    current_stage: Optional[str] = None
    eta_seconds: Optional[int] = None
    error_message: Optional[str] = None


class VideoOut(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    status: str
    checkpoint: Optional[str] = None
    file_size_mb: Optional[float] = None
    duration_seconds: Optional[float] = None
    copyright_status: str
    clips_count: int = 0
    thumbnail_url: Optional[str] = None
    download_progress: Optional[int] = None
    quality_preference: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoDetailOut(VideoOut):
    transcript: Optional[str] = None
    original_url: Optional[str] = None
    error_message: Optional[str] = None
