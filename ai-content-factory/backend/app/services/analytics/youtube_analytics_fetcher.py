"""YouTube Analytics Fetcher.

Fetches channel and video analytics data from YouTube Data API v3
and YouTube Analytics API. Implements quota management via Redis.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from loguru import logger

from app.services.analytics.models import (
    DailyStats,
    RetentionDataPoint,
    VideoAnalyticsData,
    VideoMetadata,
)

WIB = ZoneInfo("Asia/Jakarta")


def _parse_iso_duration(duration: str) -> int:
    """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
    import re
    pattern = re.compile(
        r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
    )
    m = pattern.match(duration or "PT0S")
    if not m:
        return 0
    parts = m.groupdict(default="0")
    return (
        int(parts["days"]) * 86400
        + int(parts["hours"]) * 3600
        + int(parts["minutes"]) * 60
        + int(parts["seconds"])
    )


class YouTubeAnalyticsFetcher:
    """Wraps YouTube Data API v3 + YouTube Analytics API.

    All heavy calls are run in a thread executor so they don't block
    the asyncio event loop (google-api-python-client is synchronous).
    """

    QUOTA_KEY_TEMPLATE = "yt_analytics_quota:{channel_id}:{date}"
    DAILY_QUOTA_LIMIT = 8_000   # hard stop — real limit is 10K
    REQUEST_INTERVAL = 0.1      # 100ms between requests

    def __init__(self, access_token: str, refresh_token: str, channel_id: str, redis_client: Any = None):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._channel_id = channel_id
        self._redis = redis_client

        # client_id / client_secret are required for token refresh.
        # They live in app config (env vars), not in the DB.
        try:
            from app.core.config import settings
            client_id = settings.GOOGLE_CLIENT_ID
            client_secret = settings.GOOGLE_CLIENT_SECRET
        except Exception:
            client_id = None
            client_secret = None

        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id or None,
            client_secret=client_secret or None,
        )
        self._yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        self._yta = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)

    # ── Quota Management ─────────────────────────────────────────────────────

    async def _check_quota(self, units: int = 1) -> bool:
        """Return False and log warning if quota would exceed daily limit."""
        if self._redis is None:
            return True
        today = date.today().isoformat()
        key = self.QUOTA_KEY_TEMPLATE.format(channel_id=self._channel_id, date=today)
        used = int(await self._redis.get(key) or 0)
        if used + units > self.DAILY_QUOTA_LIMIT:
            logger.warning(
                f"[Analytics] Quota limit approached for {self._channel_id}: "
                f"{used}/{self.DAILY_QUOTA_LIMIT} units. Skipping request."
            )
            return False
        await self._redis.incrby(key, units)
        await self._redis.expire(key, 86400)
        return True

    async def _run_sync(self, fn: Callable, *args, **kwargs) -> Any:
        """Run a synchronous google-api call in thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    # ── Public API ────────────────────────────────────────────────────────────

    async def fetch_channel_videos(self, max_results: int = 50) -> list[VideoMetadata]:
        """Fetch latest videos from channel via YouTube Data API."""
        if not await self._check_quota(units=2):
            return []

        try:
            # Step 1: get video IDs via search
            search_response = await self._run_sync(
                self._yt.search().list(
                    channelId=self._channel_id,
                    part="id",
                    order="date",
                    maxResults=max_results,
                    type="video",
                ).execute
            )
            video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
            if not video_ids:
                return []

            # Step 2: get full video details in one batch
            videos_response = await self._run_sync(
                self._yt.videos().list(
                    id=",".join(video_ids),
                    part="id,snippet,contentDetails,statistics",
                ).execute
            )

            results: list[VideoMetadata] = []
            for item in videos_response.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                duration = _parse_iso_duration(
                    item.get("contentDetails", {}).get("duration", "PT0S")
                )
                results.append(
                    VideoMetadata(
                        youtube_id=item["id"],
                        title=snippet.get("title", ""),
                        published_at=datetime.fromisoformat(
                            snippet.get("publishedAt", "2000-01-01T00:00:00Z").replace("Z", "+00:00")
                        ),
                        duration_seconds=duration,
                        views=int(stats.get("viewCount", 0)),
                        likes=int(stats.get("likeCount", 0)),
                        comments=int(stats.get("commentCount", 0)),
                    )
                )
            return results

        except HttpError as exc:
            logger.error(f"[Analytics] fetch_channel_videos HTTP error: {exc}")
            return []

    async def fetch_video_analytics(
        self,
        youtube_video_id: str,
        start_date: date,
        end_date: date,
    ) -> Optional[VideoAnalyticsData]:
        """Fetch detailed analytics for a single video from YouTube Analytics API."""
        if not await self._check_quota(units=3):
            return None

        metrics = (
            "views,likes,comments,shares,"
            "estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
            "subscribersGained,subscribersLost"
        )

        try:
            response = await self._run_sync(
                self._yta.reports().query(
                    ids=f"channel=={self._channel_id}",
                    startDate=start_date.isoformat(),
                    endDate=end_date.isoformat(),
                    metrics=metrics,
                    filters=f"video=={youtube_video_id}",
                ).execute
            )
            rows = response.get("rows")
            if not rows:
                return VideoAnalyticsData(youtube_video_id=youtube_video_id)

            row = rows[0]
            headers = [col["name"] for col in response.get("columnHeaders", [])]
            data = dict(zip(headers, row))

            # Traffic sources (separate request)
            await asyncio.sleep(self.REQUEST_INTERVAL)
            traffic_data = await self._fetch_traffic_sources(youtube_video_id, start_date, end_date)

            # Device types (separate request)
            await asyncio.sleep(self.REQUEST_INTERVAL)
            device_data = await self._fetch_device_types(youtube_video_id, start_date, end_date)

            return VideoAnalyticsData(
                youtube_video_id=youtube_video_id,
                views=int(data.get("views", 0)),
                likes=int(data.get("likes", 0)),
                comments=int(data.get("comments", 0)),
                shares=int(data.get("shares", 0)),
                watch_time_minutes=float(data.get("estimatedMinutesWatched", 0)),
                avg_view_duration_seconds=float(data.get("averageViewDuration", 0)),
                avg_view_percentage=float(data.get("averageViewPercentage", 0)),
                impressions=0,
                impression_ctr=0.0,
                subscribers_gained=int(data.get("subscribersGained", 0)),
                subscribers_lost=int(data.get("subscribersLost", 0)),
                traffic_sources=traffic_data,
                device_types=device_data,
            )

        except HttpError as exc:
            logger.error(f"[Analytics] fetch_video_analytics({youtube_video_id}) HTTP error: {exc}")
            return None

    async def _fetch_traffic_sources(
        self, youtube_video_id: str, start_date: date, end_date: date
    ) -> dict[str, float]:
        if not await self._check_quota(units=1):
            return {}
        try:
            response = await self._run_sync(
                self._yta.reports().query(
                    ids=f"channel=={self._channel_id}",
                    startDate=start_date.isoformat(),
                    endDate=end_date.isoformat(),
                    metrics="views",
                    dimensions="insightTrafficSourceType",
                    filters=f"video=={youtube_video_id}",
                ).execute
            )
            rows = response.get("rows", [])
            total = sum(r[1] for r in rows) or 1
            return {r[0]: round(r[1] / total * 100, 1) for r in rows}
        except HttpError:
            return {}

    async def _fetch_device_types(
        self, youtube_video_id: str, start_date: date, end_date: date
    ) -> dict[str, float]:
        if not await self._check_quota(units=1):
            return {}
        try:
            response = await self._run_sync(
                self._yta.reports().query(
                    ids=f"channel=={self._channel_id}",
                    startDate=start_date.isoformat(),
                    endDate=end_date.isoformat(),
                    metrics="views",
                    dimensions="deviceType",
                    filters=f"video=={youtube_video_id}",
                ).execute
            )
            rows = response.get("rows", [])
            total = sum(r[1] for r in rows) or 1
            return {r[0]: round(r[1] / total * 100, 1) for r in rows}
        except HttpError:
            return {}

    async def fetch_retention_curve(
        self, youtube_video_id: str
    ) -> list[RetentionDataPoint]:
        """Fetch audience retention curve. Available only for videos with enough views."""
        if not await self._check_quota(units=1):
            return []
        try:
            response = await self._run_sync(
                self._yta.reports().query(
                    ids=f"channel=={self._channel_id}",
                    startDate="2020-01-01",
                    endDate=date.today().isoformat(),
                    metrics="audienceWatchRatio,relativeRetentionPerformance",
                    dimensions="elapsedVideoTimeRatio",
                    filters=f"video=={youtube_video_id}",
                ).execute
            )
            rows = response.get("rows", [])
            if not rows:
                return []

            # Fetch video duration to convert ratios to seconds
            duration = await self._get_video_duration(youtube_video_id)

            points: list[RetentionDataPoint] = []
            for row in rows:
                elapsed = float(row[0])
                retention = float(row[1]) if row[1] is not None else 0.0
                relative = float(row[2]) if len(row) > 2 and row[2] is not None else 1.0
                points.append(
                    RetentionDataPoint(
                        elapsed_ratio=round(elapsed, 4),
                        retention_ratio=round(retention, 4),
                        relative_performance=round(relative, 4),
                        timestamp_seconds=int(elapsed * duration),
                    )
                )
            return points

        except HttpError as exc:
            logger.warning(f"[Analytics] fetch_retention_curve({youtube_video_id}) HTTP error: {exc}")
            return []

    async def _get_video_duration(self, youtube_video_id: str) -> int:
        """Fetch video duration seconds. Used for retention curve timestamp calculation."""
        try:
            response = await self._run_sync(
                self._yt.videos().list(
                    id=youtube_video_id,
                    part="contentDetails",
                ).execute
            )
            items = response.get("items", [])
            if items:
                return _parse_iso_duration(items[0]["contentDetails"]["duration"])
        except HttpError:
            pass
        return 0

    async def fetch_channel_daily_stats(
        self, start_date: date, end_date: date
    ) -> list[DailyStats]:
        """Fetch channel-level aggregate stats per day."""
        if not await self._check_quota(units=1):
            return []
        try:
            response = await self._run_sync(
                self._yta.reports().query(
                    ids=f"channel=={self._channel_id}",
                    startDate=start_date.isoformat(),
                    endDate=end_date.isoformat(),
                    metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost",
                    dimensions="day",
                ).execute
            )
            rows = response.get("rows", [])
            results: list[DailyStats] = []
            for row in rows:
                row_date = date.fromisoformat(row[0])
                results.append(
                    DailyStats(
                        date=row_date,
                        views=int(row[1]),
                        watch_time_minutes=float(row[2]),
                        subscribers_gained=int(row[3]),
                        subscribers_lost=int(row[4]),
                    )
                )
            return results
        except HttpError as exc:
            logger.error(f"[Analytics] fetch_channel_daily_stats HTTP error: {exc}")
            return []

    async def batch_fetch_all_videos_analytics(
        self,
        video_ids: list[str],
        start_date: date,
        end_date: date,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> dict[str, VideoAnalyticsData]:
        """Batch fetch analytics for multiple videos, 10 per batch with rate limiting."""
        results: dict[str, VideoAnalyticsData] = {}
        batch_size = 10
        total = len(video_ids)

        for i in range(0, total, batch_size):
            chunk = video_ids[i : i + batch_size]
            tasks = [
                self.fetch_video_analytics(vid_id, start_date, end_date)
                for vid_id in chunk
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for vid_id, result in zip(chunk, batch_results):
                if isinstance(result, VideoAnalyticsData):
                    results[vid_id] = result
                elif isinstance(result, Exception):
                    logger.warning(f"[Analytics] batch fetch failed for {vid_id}: {result}")

            if progress_callback:
                progress_callback(min(i + batch_size, total), total)

            await asyncio.sleep(self.REQUEST_INTERVAL)

        return results


def detect_peak_moments(
    points: list[RetentionDataPoint], min_rise: float = 0.02
) -> list[dict[str, Any]]:
    """Detect moments where retention rises (re-watches / seek backs)."""
    peaks = []
    for i in range(1, len(points)):
        delta = points[i].retention_ratio - points[i - 1].retention_ratio
        if delta >= min_rise:
            peaks.append(
                {
                    "elapsed_ratio": points[i].elapsed_ratio,
                    "retention_ratio": points[i].retention_ratio,
                    "timestamp_seconds": points[i].timestamp_seconds,
                    "rise": round(delta, 4),
                }
            )
    return peaks


def detect_drop_offs(
    points: list[RetentionDataPoint], min_drop_pct: float = 15.0
) -> list[dict[str, Any]]:
    """Detect large drop-off moments (>15% loss in one interval)."""
    drops = []
    for i in range(1, len(points)):
        prev = points[i - 1].retention_ratio
        if prev <= 0:
            continue
        drop_pct = (prev - points[i].retention_ratio) / prev * 100
        if drop_pct >= min_drop_pct:
            drops.append(
                {
                    "elapsed_ratio": points[i].elapsed_ratio,
                    "retention_ratio": points[i].retention_ratio,
                    "timestamp_seconds": points[i].timestamp_seconds,
                    "drop_pct": round(drop_pct, 1),
                }
            )
    return drops
