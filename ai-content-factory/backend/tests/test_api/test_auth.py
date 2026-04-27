"""Tests for Auth API routes (/api/v1/auth/*)."""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.user import User


# ── GET /api/v1/auth/google/login ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_google_login_returns_auth_url(client: AsyncClient):
    """Should return auth_url and state without authentication."""
    resp = await client.get("/api/v1/auth/google/login")
    assert resp.status_code == 200
    data = resp.json()
    assert "auth_url" in data
    assert "state" in data
    assert len(data["state"]) > 10  # non-trivial random token


# ── GET /api/v1/auth/me ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    """No token → 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_profile(client: AsyncClient, auth_headers: dict, test_user: User):
    """Valid JWT → returns own profile."""
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == test_user.email
    assert data["id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_me_invalid_token(client: AsyncClient):
    """Malformed token → 401."""
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_missing_bearer_scheme(client: AsyncClient, test_user: User):
    """Token without 'Bearer' prefix → 401 or 403."""
    from app.core.security import create_access_token
    token = create_access_token({"sub": str(test_user.id)})
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": token})
    assert resp.status_code in (401, 403)


# ── GET /api/v1/auth/google/callback ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_callback_missing_code(client: AsyncClient):
    """Missing 'code' query param → 422."""
    resp = await client.get("/api/v1/auth/google/callback?state=abc")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_callback_token_exchange_failure(client: AsyncClient):
    """If OAuth token exchange fails → 400."""
    with patch("app.api.routes.auth.exchange_code_for_tokens", side_effect=Exception("bad code")):
        resp = await client.get("/api/v1/auth/google/callback?code=bad&state=xyz")
    assert resp.status_code == 400
    assert "token exchange" in resp.json()["detail"].lower()
