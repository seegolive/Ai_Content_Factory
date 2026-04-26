"""Video Pydantic schemas."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator


class VideoUploadResponse(BaseModel):
    video_id: uuid.UUID
    status: str
    message: str


class VideoFromUrlRequest(BaseModel):
    youtube_url: str
    youtube_account_id: Optional[uuid.UUID] = None

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        if not ("youtube.com/watch" in v or "youtu.be/" in v):
            raise ValueError("Must be a valid YouTube URL")
        return v


class VideoStatusResponse(BaseModel):
    video_id: uuid.UUID
    status: str
    checkpoint: Optional[str] = None
    progress_percent: int
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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoDetailOut(VideoOut):
    transcript: Optional[str] = None
    original_url: Optional[str] = None
    error_message: Optional[str] = None
