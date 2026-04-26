"""ACRCloud-based copyright detection service."""
import asyncio
import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger

from app.core.config import settings


@dataclass
class CopyrightResult:
    is_flagged: bool
    matched_music: Optional[str]
    artist: Optional[str]
    confidence: float
    status: str  # clean | flagged | uncertain


class CopyrightCheckService:

    async def check_audio(self, video_path: str) -> CopyrightResult:
        """Extract audio sample and check against ACRCloud."""
        if not settings.ACRCLOUD_ACCESS_KEY:
            logger.warning("ACRCloud not configured, skipping copyright check")
            return CopyrightResult(
                is_flagged=False, matched_music=None, artist=None,
                confidence=0.0, status="unchecked"
            )

        try:
            audio_bytes = await self.extract_audio_sample(video_path)
            return await self._query_acrcloud(audio_bytes)
        except Exception as e:
            logger.error(f"Copyright check failed for {video_path}: {e}")
            return CopyrightResult(
                is_flagged=False, matched_music=None, artist=None,
                confidence=0.0, status="uncertain"
            )

    async def extract_audio_sample(self, video_path: str, duration: int = 30) -> bytes:
        """Extract audio segment from the middle of the video as WAV bytes."""
        # Get video duration first
        probe_cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            video_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *probe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        total_duration = float(stdout.decode().strip() or "0")
        start = max(0, (total_duration / 2) - (duration / 2))

        # Extract audio
        extract_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(duration),
            "-i", video_path,
            "-ac", "1",
            "-ar", "44100",
            "-f", "wav",
            "pipe:1",
        ]
        proc = await asyncio.create_subprocess_exec(
            *extract_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        return stdout

    async def _query_acrcloud(self, audio_bytes: bytes) -> CopyrightResult:
        """Send audio to ACRCloud API."""
        timestamp = str(int(time.time()))
        string_to_sign = "\n".join([
            "POST",
            "/v1/identify",
            settings.ACRCLOUD_ACCESS_KEY,
            "audio",
            "1",
            timestamp,
        ])
        signature = base64.b64encode(
            hmac.new(
                settings.ACRCLOUD_ACCESS_SECRET.encode(),
                string_to_sign.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://{settings.ACRCLOUD_HOST}/v1/identify",
                data={
                    "access_key": settings.ACRCLOUD_ACCESS_KEY,
                    "sample_bytes": str(len(audio_bytes)),
                    "timestamp": timestamp,
                    "signature": signature,
                    "data_type": "audio",
                    "signature_version": "1",
                },
                files={"sample": ("sample.wav", audio_bytes, "audio/wav")},
            )
            data = resp.json()

        status_code = data.get("status", {}).get("code", -1)
        if status_code == 0:
            music = data.get("metadata", {}).get("music", [])
            if music:
                track = music[0]
                return CopyrightResult(
                    is_flagged=True,
                    matched_music=track.get("title"),
                    artist=track.get("artists", [{}])[0].get("name"),
                    confidence=float(track.get("score", 0)) / 100,
                    status="flagged",
                )
        elif status_code == 1001:  # No result
            return CopyrightResult(is_flagged=False, matched_music=None, artist=None, confidence=0.0, status="clean")

        return CopyrightResult(is_flagged=False, matched_music=None, artist=None, confidence=0.0, status="uncertain")
