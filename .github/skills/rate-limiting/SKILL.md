---
name: rate-limiting
description: "Add rate limiting to FastAPI endpoints in this project. Use when: implementing Gap #2 (rate limiting on upload endpoints), protecting against abuse, limiting API calls per user, or throttling expensive operations. Covers slowapi integration, per-user limits, and custom error responses."
argument-hint: "e.g. 'add rate limit to /videos/upload', '5 uploads per hour per user', 'rate limit all API routes'"
---

# Rate Limiting Skill

## When to Use
- Gap #2 from `copilot-instructions.md`: upload endpoints have no rate limit
- `/videos/upload` and `/videos/from-url` need ≤5 uploads/hour/user
- Protecting expensive endpoints (transcription, AI scoring triggers)
- Preventing API abuse

## Project Context

```
Framework: FastAPI + slowapi (Starlette-compatible)
Auth: JWT-based, user extracted via get_current_user dependency
Target endpoints:
  POST /api/v1/videos/upload      → ≤5/hour per user
  POST /api/v1/videos/from-url    → ≤5/hour per user
  POST /api/v1/clips/{id}/publish → ≤20/hour per user
```

## Procedure

### 1. Install slowapi

Add to `backend/requirements.txt`:
```
slowapi==0.1.9
```

Rebuild backend:
```bash
docker compose build backend && docker compose up -d backend
```

### 2. Configure Limiter in `main.py`

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

# Use JWT user ID as key (not IP) for authenticated routes
def get_user_id_key(request: Request) -> str:
    # Extract user_id from JWT token for per-user limiting
    # Falls back to IP for unauthenticated requests
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(auth[7:])
            return str(payload.get("sub", get_remote_address(request)))
        except Exception:
            pass
    return get_remote_address(request)

limiter = Limiter(key_func=get_user_id_key)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### 3. Apply Rate Limits to Routes

File: `backend/app/api/routes/videos.py`

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

# Get limiter from app state
def get_limiter(request: Request) -> Limiter:
    return request.app.state.limiter

@router.post("/upload", status_code=202)
@limiter.limit("5/hour")
async def upload_video(
    request: Request,  # REQUIRED by slowapi — must be first param
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ...

@router.post("/from-url", status_code=202)
@limiter.limit("5/hour")
async def upload_from_url(
    request: Request,
    payload: VideoFromURLRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ...
```

### 4. Custom Error Response (JSON instead of plain text)

```python
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse

async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded. Maximum 5 uploads per hour.",
            "retry_after": exc.retry_after,  # seconds until reset
        },
        headers={"Retry-After": str(exc.retry_after)},
    )

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
```

### 5. Rate Limit Headers (Optional but helpful for clients)

slowapi automatically adds these headers to responses:
```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1714320000
```

No additional code needed.

### 6. Storage Backend (Redis for distributed)

Default: in-memory (resets on restart). For persistent limits across restarts:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_user_id_key,
    storage_uri="redis://redis:6379/1",  # use DB 1 to separate from Celery
)
```

Add to `backend/.env.example`:
```
RATE_LIMIT_STORAGE_URI=redis://redis:6379/1
```

### 7. Recommended Limits Per Endpoint

| Endpoint | Limit | Reason |
|----------|-------|--------|
| `POST /videos/upload` | 5/hour | Heavy: GPU + storage |
| `POST /videos/from-url` | 5/hour | Heavy: download + GPU |
| `POST /clips/{id}/publish` | 20/hour | YouTube API quota |
| `POST /auth/login` | 10/minute | Brute force protection |
| `GET /videos` | 100/minute | Light, but prevent scraping |

## Testing Rate Limits

```python
# test_rate_limit.py
import pytest

@pytest.mark.asyncio
async def test_upload_rate_limit(client, auth_headers):
    """Should reject 6th upload within 1 hour."""
    for i in range(5):
        resp = await client.post("/api/v1/videos/upload", ...)
        assert resp.status_code != 429

    # 6th request should be rate limited
    resp = await client.post("/api/v1/videos/upload", ...)
    assert resp.status_code == 429
    assert "retry_after" in resp.json()
```

## Anti-patterns
- Don't use IP-based limiting for authenticated endpoints (shared NAT/proxy)
- Don't store limits in PostgreSQL (too slow — use Redis)
- Don't set limits too low for dev/test environments (use env var to disable)
- Don't forget to add `request: Request` as first param — slowapi requires it
