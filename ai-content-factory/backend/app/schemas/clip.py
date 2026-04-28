"""Clip Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ClipOut(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: float
    end_time: float
    duration: Optional[float] = None
    viral_score: Optional[int] = None
    moment_type: Optional[str] = None
    hook_text: Optional[str] = None
    hashtags: list[str] = []
    thumbnail_path: Optional[str] = None
    clip_path: Optional[str] = None
    clip_path_horizontal: Optional[str] = None
    clip_path_vertical: Optional[str] = None
    clip_path_square: Optional[str] = None
    format_generated: dict = {}
    format: str
    qc_status: str
    qc_issues: list = []
    review_status: str
    reviewed_at: Optional[datetime] = None
    platform_status: dict = {}
    publish_settings: dict = {}
    ai_provider_used: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    note: Optional[str] = None


class ClipBulkReviewRequest(BaseModel):
    clip_ids: list[uuid.UUID] = Field(min_length=1)
    action: Literal["approve", "reject"]


class ClipUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    hashtags: Optional[list[str]] = None


class ClipPublishSettingsRequest(BaseModel):
    """Save YouTube publish settings before queuing."""

    title: Optional[str] = None
    description: Optional[str] = None
    hashtags: Optional[list[str]] = None
    privacy: Literal["public", "unlisted", "private"] = "unlisted"
    category: Optional[str] = None  # YouTube category ID, e.g. "20" for Gaming


class ClipPublishRequest(BaseModel):
    platforms: list[str] = Field(default=["youtube"])
    youtube_account_id: Optional[uuid.UUID] = None
    privacy: Literal["public", "unlisted", "private"] = "unlisted"
