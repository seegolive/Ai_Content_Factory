---
name: write-tests
description: "Write pytest tests for this project. Use when: adding test coverage for services, testing API endpoints, writing Celery task tests, mocking external services (Whisper, YouTube, OpenRouter, ACRCloud). Covers backend unit tests, API integration tests, and Celery worker tests."
argument-hint: "e.g. 'test clips bulk review endpoint' or 'test ai_brain fallback chain'"
---

# Write Tests

## When to Use
- Adding coverage for new or existing backend code
- Testing a new API endpoint (after using `/add-api-endpoint`)
- Writing Celery task integration tests
- Increasing coverage for the 40% currently untested code

## Test Infrastructure

**conftest.py** provides these fixtures — always use them:
- `client` — `AsyncClient` with base_url
- `auth_headers` — `{"Authorization": "Bearer <test-token>"}`
- `db_session` — async SQLAlchemy session
- `test_user` — seeded `User` object

**Run tests:**
```bash
make test                          # all tests
docker compose exec backend pytest tests/test_api/test_clips.py -v
docker compose exec backend pytest -k "test_bulk" -v  # filter by name
```

## Patterns by Test Type

### API Endpoint Test
File: `backend/tests/test_api/test_<domain>.py`
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_my_endpoint_success(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/clips/review/bulk",
        headers=auth_headers,
        json={"clip_ids": ["uuid-1", "uuid-2"], "action": "approved"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["updated_count"] == 2

@pytest.mark.asyncio
async def test_my_endpoint_unauthorized(client: AsyncClient):
    response = await client.post("/api/v1/clips/review/bulk", json={})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_my_endpoint_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/videos/nonexistent-uuid", headers=auth_headers)
    assert response.status_code == 404
```

### Service Unit Test
File: `backend/tests/test_services/test_<service>.py`
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_ai_brain_fallback(mock_db):
    """Test that AI brain falls back to second provider when first fails."""
    with patch("app.services.ai_brain.groq_client") as mock_groq:
        mock_groq.chat.completions.create.side_effect = Exception("Groq down")
        with patch("app.services.ai_brain.gemini_client") as mock_gemini:
            mock_gemini.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content='{"clips": []}'))]
            )
            result = await ai_brain.score_clips("transcript text", "video-id")
            assert result == []  # empty list on fallback
            mock_gemini.chat.completions.create.assert_called_once()
```

### Celery Task Test
File: `backend/tests/test_workers/test_pipeline.py`
```python
import pytest

@pytest.mark.celery(result_backend="redis://localhost:6379/0")
def test_pipeline_checkpoint_skip(celery_worker, db_with_video_at_checkpoint):
    """Test that pipeline skips already-completed stages."""
    video = db_with_video_at_checkpoint("transcript_done")
    # Call pipeline — should skip Stage 1 (transcription)
    with patch("app.workers.tasks.pipeline.transcription_service") as mock_ts:
        process_video_pipeline.apply(args=[str(video.id)])
        mock_ts.transcribe.assert_not_called()  # skipped because checkpoint passed
```

**Note:** Celery tests require `celery_worker` fixture and Redis running. Mark with `@pytest.mark.celery`.

### Mocking External Services

| Service | Mock target | What to return |
|---------|-------------|----------------|
| Whisper | `app.services.transcription.WhisperModel` | `MagicMock(segments=[...])` |
| OpenRouter/Groq | `openai.AsyncOpenAI` | `MagicMock(choices=[...])` |
| YouTube API | `googleapiclient.discovery.build` | `MagicMock()` with chained calls |
| ACRCloud | `app.services.copyright_check.ACRCloudClient` | `MagicMock(recognize=...)` |
| FFmpeg | `subprocess.run` | `MagicMock(returncode=0)` |

### Standard Test Structure
```python
# Arrange
video = await create_test_video(db_session, user_id=test_user.id)

# Act
response = await client.get(f"/api/v1/videos/{video.id}", headers=auth_headers)

# Assert
assert response.status_code == 200
assert response.json()["id"] == str(video.id)
```

## What's Missing (prioritize these)

1. `tests/test_workers/test_pipeline.py` — **doesn't exist** — highest priority
2. `tests/test_api/test_clips.py` — bulk review race condition test
3. `tests/test_services/test_ai_brain.py` — provider fallback chain
4. `tests/test_api/test_videos.py` — from-url download failure handling
5. Edge cases: invalid UUIDs, empty payloads, expired JWT tokens

## Coverage Report
```bash
docker compose exec backend pytest --cov=app --cov-report=html tests/
# Opens coverage report in backend/htmlcov/index.html
```
