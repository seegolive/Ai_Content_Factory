"""Dataclasses and typed models for analytics services.

These are internal data transfer objects — not SQLAlchemy models.
Used between services and tasks to avoid tight coupling to ORM.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional


@dataclass
class VideoMetadata:
    """Lightweight video info fetched from YouTube Data API."""

    youtube_id: str
    title: str
    published_at: datetime
    duration_seconds: int
    views: int
    likes: int
    comments: int
    # Internal DB id — populated when matched against local videos table
    internal_id: Optional[str] = None


@dataclass
class RetentionDataPoint:
    elapsed_ratio: float        # 0.0 – 1.0 (progress through video)
    retention_ratio: float      # 0.0 – 1.0 (fraction still watching)
    relative_performance: float  # compared to similar videos
    timestamp_seconds: int       # absolute second in video


@dataclass
class VideoAnalyticsData:
    youtube_video_id: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    watch_time_minutes: float = 0.0
    avg_view_duration_seconds: float = 0.0
    avg_view_percentage: float = 0.0
    impressions: int = 0
    impression_ctr: float = 0.0
    subscribers_gained: int = 0
    subscribers_lost: int = 0
    revenue_usd: Optional[float] = None
    traffic_sources: dict[str, Any] = field(default_factory=dict)
    device_types: dict[str, Any] = field(default_factory=dict)
    top_geographies: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DailyStats:
    date: date
    views: int = 0
    watch_time_minutes: float = 0.0
    subscribers_gained: int = 0
    subscribers_lost: int = 0

    @property
    def subscribers_net(self) -> int:
        return self.subscribers_gained - self.subscribers_lost


@dataclass
class VideoOpportunity:
    """Video that hasn't been clipped yet but has viral potential."""

    video_id: str
    youtube_video_id: str
    title: str
    duration_seconds: int
    published_at: datetime
    game_name: Optional[str]
    viral_potential_score: float    # 0–100
    estimated_clips: int
    peak_moments_count: int
    has_retention_data: bool
    recommendation: str
