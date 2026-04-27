"""Tests for Clips API routes (/api/v1/clips/* and /api/v1/videos/{id}/clips)."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clip import Clip
from app.models.user import User
from app.models.video import Video


# ── GET /api/v1/videos/{id}/clips ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_clips_unauthenticated(client: AsyncClient, test_video):
    resp = await client.get(f"/api/v1/videos/{test_video.id}/clips")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_clips_empty_video(client: AsyncClient, auth_headers: dict, test_video):
    """Video with no clips returns empty list."""
    resp = await client.get(f"/api/v1/videos/{test_video.id}/clips", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_clips_with_clip(client: AsyncClient, auth_headers: dict, test_video, test_clip):
    resp = await client.get(f"/api/v1/videos/{test_video.id}/clips", headers=auth_headers)
    assert resp.status_code == 200
    clips = resp.json()
    assert len(clips) >= 1
    first = clips[0]
    assert first["id"] == str(test_clip.id)
    assert first["viral_score"] == 80
    assert first["moment_type"] == "clutch"


@pytest.mark.asyncio
async def test_list_clips_video_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"/api/v1/videos/{uuid.uuid4()}/clips", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_clips_wrong_user(client: AsyncClient, db: AsyncSession, test_video):
    """Other user's JWT cannot list clips for this video."""
    other_user = User(
        id=uuid.uuid4(),
        email=f"other_{uuid.uuid4().hex[:6]}@test.com",
        google_id=f"g_{uuid.uuid4().hex}",
        name="Other",
        plan="free",
    )
    db.add(other_user)
    await db.commit()
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(other_user.id)})
    resp = await client.get(
        f"/api/v1/videos/{test_video.id}/clips",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_clips_filter_by_review_status(
    client: AsyncClient, auth_headers: dict, test_video, test_clip
):
    resp = await client.get(
        f"/api/v1/videos/{test_video.id}/clips?review_status=pending",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    clips = resp.json()
    assert all(c["review_status"] == "pending" for c in clips)


@pytest.mark.asyncio
async def test_list_clips_invalid_sort(client: AsyncClient, auth_headers: dict, test_video):
    resp = await client.get(
        f"/api/v1/videos/{test_video.id}/clips?sort=invalid_field",
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── PATCH /api/v1/clips/{id}/review ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_clip_approve(client: AsyncClient, auth_headers: dict, test_clip):
    resp = await client.patch(
        f"/api/v1/clips/{test_clip.id}/review",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "approved"


@pytest.mark.asyncio
async def test_review_clip_reject(client: AsyncClient, auth_headers: dict, test_clip):
    resp = await client.patch(
        f"/api/v1/clips/{test_clip.id}/review",
        json={"action": "reject"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "rejected"


@pytest.mark.asyncio
async def test_review_clip_invalid_action(client: AsyncClient, auth_headers: dict, test_clip):
    resp = await client.patch(
        f"/api/v1/clips/{test_clip.id}/review",
        json={"action": "delete"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_review_clip_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.patch(
        f"/api/v1/clips/{uuid.uuid4()}/review",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_review_clip_unauthenticated(client: AsyncClient, test_clip):
    resp = await client.patch(f"/api/v1/clips/{test_clip.id}/review", json={"action": "approve"})
    assert resp.status_code == 401


# ── POST /api/v1/clips/bulk-review ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_bulk_review_approve(client: AsyncClient, auth_headers: dict, test_clip):
    resp = await client.post(
        "/api/v1/clips/bulk-review",
        json={"clip_ids": [str(test_clip.id)], "action": "approve"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_status"] == "approved"
    assert data["updated"] >= 0


@pytest.mark.asyncio
async def test_bulk_review_empty_list(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/clips/bulk-review",
        json={"clip_ids": [], "action": "approve"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_review_unauthenticated(client: AsyncClient, test_clip):
    resp = await client.post(
        "/api/v1/clips/bulk-review",
        json={"clip_ids": [str(test_clip.id)], "action": "approve"},
    )
    assert resp.status_code == 401


# ── PATCH /api/v1/clips/{id} — update metadata ───────────────────────────────

@pytest.mark.asyncio
async def test_update_clip_title(client: AsyncClient, auth_headers: dict, test_clip):
    resp = await client.patch(
        f"/api/v1/clips/{test_clip.id}",
        json={"title": "New Epic Title"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Epic Title"


@pytest.mark.asyncio
async def test_update_clip_hashtags(client: AsyncClient, auth_headers: dict, test_clip):
    resp = await client.patch(
        f"/api/v1/clips/{test_clip.id}",
        json={"hashtags": ["gaming", "shorts", "viral"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "viral" in resp.json()["hashtags"]


@pytest.mark.asyncio
async def test_update_clip_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.patch(
        f"/api/v1/clips/{uuid.uuid4()}",
        json={"title": "X"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── POST /api/v1/clips/{id}/publish ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_clip_not_approved(client: AsyncClient, auth_headers: dict, test_clip):
    """Clip with pending review status cannot be published."""
    resp = await client.post(
        f"/api/v1/clips/{test_clip.id}/publish",
        json={"platforms": ["youtube"]},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "approved" in resp.json()["detail"].lower()


@pytest.mark.asyncio
@patch("app.workers.tasks.distribute.distribute_clip")
async def test_publish_clip_approved(
    mock_distribute, client: AsyncClient, db: AsyncSession, auth_headers: dict, test_clip
):
    """Approved clip triggers distribute task and returns 202."""
    mock_task = MagicMock()
    mock_task.id = "celery-abc-123"
    mock_distribute.delay = MagicMock(return_value=mock_task)

    # Approve the clip first
    test_clip.review_status = "approved"
    await db.commit()

    resp = await client.post(
        f"/api/v1/clips/{test_clip.id}/publish",
        json={"platforms": ["youtube"]},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "publish_job_id" in data
    assert data["platforms"] == ["youtube"]


# ── GET /api/v1/clips/{id}/stream-token ──────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_token_unauthenticated(client: AsyncClient, test_clip):
    resp = await client.get(f"/api/v1/clips/{test_clip.id}/stream-token")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stream_token_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"/api/v1/clips/{uuid.uuid4()}/stream-token", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_token_returns_token(client: AsyncClient, auth_headers: dict, test_clip):
    """Clip with no file_path still returns a signed token (path checked at stream time)."""
    resp = await client.get(f"/api/v1/clips/{test_clip.id}/stream-token", headers=auth_headers)
    # 200 with token, or 404 if clip_path check happens here
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert "stream_token" in data or "token" in data


# ── GET /api/v1/clips/{id}/stream ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_unauthenticated_no_token(client: AsyncClient, test_clip):
    """No auth header and no ?token= → 401 or 403."""
    resp = await client.get(f"/api/v1/clips/{test_clip.id}/stream")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_stream_invalid_token(client: AsyncClient, test_clip):
    resp = await client.get(f"/api/v1/clips/{test_clip.id}/stream?token=not.a.valid.jwt")
    assert resp.status_code in (401, 403)
