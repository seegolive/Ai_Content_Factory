"""YouTube Data API v3 service."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from app.core.config import settings


@dataclass
class ChannelInfo:
    channel_id: str
    channel_name: str
    subscriber_count: int
    thumbnail_url: Optional[str]


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
