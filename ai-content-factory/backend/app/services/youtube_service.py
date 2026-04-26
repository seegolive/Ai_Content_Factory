"""YouTube Data API v3 service."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from loguru import logger

from app.core.config import settings


@dataclass
class ChannelInfo:
    channel_id: str
    channel_name: str
    subscriber_count: int
    thumbnail_url: Optional[str]


@dataclass
class VideoStat:
    video_id: str
    title: str
    published_at: str
    thumbnail_url: Optional[str]
    views: int
    likes: int
    comments: int
    duration_seconds: int


@dataclass
class ChannelAnalytics:
    channel_id: str
    channel_name: str
    thumbnail_url: Optional[str]
    subscriber_count: int
    total_views: int
    total_videos: int
    # per-video stats for the latest N videos
    recent_videos: List[VideoStat] = field(default_factory=list)
    # top 5 by views
    top_videos: List[VideoStat] = field(default_factory=list)


class YouTubeService:

    def _build_service(self, access_token: str):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(token=access_token)
        return build("youtube", "v3", credentials=creds)

    async def get_channel_info(self, access_token: str) -> ChannelInfo:
        """Fetch authenticated user's channel info."""
        import asyncio
        from functools import partial

        def _fetch():
            service = self._build_service(access_token)
            resp = service.channels().list(
                part="snippet,statistics", mine=True
            ).execute()
            if not resp.get("items"):
                raise ValueError("No YouTube channel found for this account")
            item = resp["items"][0]
            return ChannelInfo(
                channel_id=item["id"],
                channel_name=item["snippet"]["title"],
                subscriber_count=int(item["statistics"].get("subscriberCount", 0)),
                thumbnail_url=item["snippet"]["thumbnails"].get("default", {}).get("url"),
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch)

    async def get_channel_analytics(self, access_token: str, max_videos: int = 20) -> ChannelAnalytics:
        """Fetch channel KPIs + per-video stats using youtube.readonly scope."""
        import asyncio
        import re

        def _iso8601_to_seconds(duration: str) -> int:
            """Convert ISO 8601 duration (PT4M13S) to seconds."""
            match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
            if not match:
                return 0
            h = int(match.group(1) or 0)
            m = int(match.group(2) or 0)
            s = int(match.group(3) or 0)
            return h * 3600 + m * 60 + s

        def _fetch():
            service = self._build_service(access_token)

            # 1. Channel-level stats
            ch_resp = service.channels().list(
                part="snippet,statistics,contentDetails", mine=True
            ).execute()
            if not ch_resp.get("items"):
                raise ValueError("No YouTube channel found for this account")
            ch = ch_resp["items"][0]
            ch_stats = ch["statistics"]
            uploads_playlist_id = ch["contentDetails"]["relatedPlaylists"]["uploads"]
            channel_id = ch["id"]
            channel_name = ch["snippet"]["title"]
            thumbnail_url = ch["snippet"]["thumbnails"].get("default", {}).get("url")
            subscriber_count = int(ch_stats.get("subscriberCount", 0))
            total_views = int(ch_stats.get("viewCount", 0))
            total_videos = int(ch_stats.get("videoCount", 0))

            # 2. Fetch latest video IDs from uploads playlist
            video_ids: list[str] = []
            next_page = None
            while len(video_ids) < max_videos:
                pl_kwargs: dict = dict(
                    part="contentDetails",
                    playlistId=uploads_playlist_id,
                    maxResults=min(50, max_videos - len(video_ids)),
                )
                if next_page:
                    pl_kwargs["pageToken"] = next_page
                pl_resp = service.playlistItems().list(**pl_kwargs).execute()
                for item in pl_resp.get("items", []):
                    vid_id = item["contentDetails"]["videoId"]
                    video_ids.append(vid_id)
                next_page = pl_resp.get("nextPageToken")
                if not next_page:
                    break

            if not video_ids:
                return ChannelAnalytics(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    thumbnail_url=thumbnail_url,
                    subscriber_count=subscriber_count,
                    total_views=total_views,
                    total_videos=total_videos,
                )

            # 3. Fetch per-video stats in batches of 50
            video_stats: list[VideoStat] = []
            for i in range(0, len(video_ids), 50):
                batch = video_ids[i:i + 50]
                v_resp = service.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(batch),
                ).execute()
                for v in v_resp.get("items", []):
                    vs = v["statistics"]
                    video_stats.append(VideoStat(
                        video_id=v["id"],
                        title=v["snippet"]["title"],
                        published_at=v["snippet"]["publishedAt"],
                        thumbnail_url=v["snippet"]["thumbnails"].get("medium", {}).get("url"),
                        views=int(vs.get("viewCount", 0)),
                        likes=int(vs.get("likeCount", 0)),
                        comments=int(vs.get("commentCount", 0)),
                        duration_seconds=_iso8601_to_seconds(
                            v["contentDetails"].get("duration", "PT0S")
                        ),
                    ))

            # Sort by published date for "recent", by views for "top"
            recent = sorted(video_stats, key=lambda v: v.published_at, reverse=True)
            top = sorted(video_stats, key=lambda v: v.views, reverse=True)[:5]

            return ChannelAnalytics(
                channel_id=channel_id,
                channel_name=channel_name,
                thumbnail_url=thumbnail_url,
                subscriber_count=subscriber_count,
                total_views=total_views,
                total_videos=total_videos,
                recent_videos=recent,
                top_videos=top,
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch)

    async def upload_video(
        self,
        clip_path: str,
        title: str,
        description: str,
        tags: list[str],
        access_token: str,
        privacy: str = "unlisted",
    ) -> str:
        """Upload video to YouTube using resumable upload. Returns youtube_video_id."""
        import asyncio
        from functools import partial

        def _upload():
            from googleapiclient.http import MediaFileUpload

            service = self._build_service(access_token)
            body = {
                "snippet": {
                    "title": title[:100],
                    "description": description[:5000],
                    "tags": tags[:500],
                    "categoryId": "22",  # People & Blogs
                },
                "status": {"privacyStatus": privacy},
            }
            media = MediaFileUpload(clip_path, chunksize=1024 * 1024, resumable=True)
            request = service.videos().insert(
                part=",".join(body.keys()), body=body, media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logger.info(f"YouTube upload progress: {int(status.progress() * 100)}%")

            return response["id"]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _upload)

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Refresh expired access token."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def check_upload_quota(self, access_token: str) -> bool:
        """Check if upload quota is available (rough estimate based on date)."""
        # YouTube API quota resets at midnight Pacific. Each upload ≈ 1600 units.
        # Max ~6 uploads/day on free quota. This is a placeholder — real tracking
        # needs to store quota usage per account in DB.
        return True
