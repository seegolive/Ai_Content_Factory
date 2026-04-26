"""Tests for Video API endpoints."""
import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.models.video import Video


@pytest.mark.asyncio
async def test_upload_video_unauthenticated(client: AsyncClient):
    """Upload without token should return 401."""
    resp = await client.post(
        "/api/v1/videos/upload",
        files={"file": ("test.mp4", io.BytesIO(b"\x00" * 100), "video/mp4")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_videos_empty(client: AsyncClient, auth_headers: dict):
    """New user has no videos."""
    resp = await client.get("/api/v1/videos", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_upload_video_invalid_format(client: AsyncClient, auth_headers: dict):
    """Uploading a non-video file should return 400."""
    resp = await client.post(
        "/api/v1/videos/upload",
        files={"file": ("doc.pdf", io.BytesIO(b"not a video"), "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Unsupported format" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_video_status_not_found(client: AsyncClient, auth_headers: dict):
    """Status for non-existent video returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/videos/{fake_id}/status", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_from_url_invalid(client: AsyncClient, auth_headers: dict):
    """Non-YouTube URL should fail validation."""
    resp = await client.post(
        "/api/v1/videos/from-url",
        json={"youtube_url": "https://example.com/not-youtube"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
@patch("app.api.routes.videos.process_video_pipeline")
async def test_upload_video_success(mock_task, client: AsyncClient, auth_headers: dict, tmp_path):
    """Valid MP4 upload should create a video record and return 202."""
    mock_task.delay = MagicMock(return_value=MagicMock(id="celery-task-id"))

    video_bytes = b"\x00" * 100
    resp = await client.post(
        "/api/v1/videos/upload",
        files={"file": ("video.mp4", io.BytesIO(video_bytes), "video/mp4")},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "video_id" in data
    assert data["status"] == "queued"
