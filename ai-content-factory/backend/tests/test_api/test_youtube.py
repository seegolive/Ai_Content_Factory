"""Tests for YouTube API routes (/api/v1/youtube/*)."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.video import YoutubeAccount


# ── Fixtures ─────────────────────────────────────────────────────────────────

async def _create_yt_account(db: AsyncSession, user: User, **kwargs) -> YoutubeAccount:
    account = YoutubeAccount(
        id=uuid.uuid4(),
        user_id=user.id,
        channel_id=kwargs.get("channel_id", f"UC{uuid.uuid4().hex[:12]}"),
        channel_name=kwargs.get("channel_name", "Seego GG"),
        access_token=kwargs.get("access_token", "yt-token-123"),
        refresh_token=kwargs.get("refresh_token", "yt-refresh-123"),
    )
    db.add(account)
    await db.commit()
    return account


# ── GET /api/v1/youtube/stats ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_youtube_stats_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/youtube/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_youtube_stats_no_account(client: AsyncClient, auth_headers: dict):
    """User with no YouTube account returns connected=False."""
    resp = await client.get("/api/v1/youtube/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["accounts"] == []


@pytest.mark.asyncio
async def test_youtube_stats_with_account(
    client: AsyncClient, db: AsyncSession, auth_headers: dict, test_user: User
):
    """User with YouTube account calls yt_service.get_channel_info."""
    await _create_yt_account(db, test_user)

    mock_info = MagicMock()
    mock_info.channel_id = "UC123"
    mock_info.channel_name = "Seego GG"
    mock_info.subscriber_count = 5000
    mock_info.thumbnail_url = "https://yt.img/thumb.jpg"

    with patch(
        "app.api.routes.youtube.yt_service.get_channel_info",
        new=AsyncMock(return_value=mock_info),
    ):
        resp = await client.get("/api/v1/youtube/stats", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    accounts = data["accounts"]
    assert len(accounts) >= 1
    assert accounts[0]["channel_name"] == "Seego GG"
    assert accounts[0]["subscriber_count"] == 5000


@pytest.mark.asyncio
async def test_youtube_stats_expired_token_with_refresh(
    client: AsyncClient, db: AsyncSession, auth_headers: dict, test_user: User
):
    """If access token expired, should try refreshing and succeed."""
    await _create_yt_account(db, test_user, access_token="expired-token")

    mock_info = MagicMock()
    mock_info.channel_id = "UC999"
    mock_info.channel_name = "Seego GG"
    mock_info.subscriber_count = 1000
    mock_info.thumbnail_url = ""

    with patch(
        "app.api.routes.youtube.yt_service.get_channel_info",
        side_effect=[Exception("token expired"), mock_info],
    ) as mock_get, patch(
        "app.api.routes.youtube.yt_service.refresh_access_token",
        new=AsyncMock(return_value="new-access-token"),
    ):
        # First call raises (expired), second call (after refresh) succeeds
        mock_get.side_effect = [Exception("token expired"), mock_info]
        resp = await client.get("/api/v1/youtube/stats", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True


@pytest.mark.asyncio
async def test_youtube_stats_expired_token_no_refresh(
    client: AsyncClient, db: AsyncSession, auth_headers: dict, test_user: User
):
    """Expired token with no refresh_token returns error message in account entry."""
    await _create_yt_account(db, test_user, access_token="expired", refresh_token=None)

    with patch(
        "app.api.routes.youtube.yt_service.get_channel_info",
        side_effect=Exception("token expired"),
    ):
        resp = await client.get("/api/v1/youtube/stats", headers=auth_headers)

    assert resp.status_code == 200
    accounts = resp.json()["accounts"]
    assert any("error" in a for a in accounts)
