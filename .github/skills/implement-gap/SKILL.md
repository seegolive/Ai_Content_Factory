---
name: implement-gap
description: "Implement a known gap or missing feature in this project. Use when: fixing known issues from copilot-instructions.md section 13, implementing missing features like game_detector, rate limiting, file cleanup, bulk race condition fix, notification fallback, retry UI, or form validation. Includes brainstorm-plan-implement-test workflow."
argument-hint: "Gap number or name, e.g. '1' or 'game_detector' or 'rate limiting'"
---

# Implement Known Gap

## When to Use
- Working on any item from **Section 13 (Known Gaps)** in `copilot-instructions.md`
- Implementing a missing service, feature, or fix identified during code review
- Resolving a TODO/FIXME in the codebase

## Known Gaps Quick Reference

Load [copilot-instructions.md](../../.github/copilot-instructions.md) Section 13 for the full list. Summary:

| # | Gap | Priority | Complexity |
|---|-----|----------|------------|
| 1 | `game_detector.py` MISSING | 🔴 Critical | High — use `/implement-game-detector` skill |
| 2 | Rate limiting on upload endpoints | 🔴 Critical | Low |
| 3 | Secure clip streaming (signed URLs) | 🔴 Critical | Medium |
| 4 | Temp file cleanup after pipeline | 🔴 Critical | Low |
| 5 | Bulk clip race condition (SELECT FOR UPDATE) | 🔴 Critical | Low |
| 6 | YouTube token refresh failure notification | 🟡 Medium | Medium |
| 7 | Pipeline retry UI button | 🟡 Medium | Medium |
| 8 | Client-side form validation (Zod) | 🟡 Medium | Low |
| 9 | In-app notifications | 🟡 Medium | High |
| 10 | Celery pipeline integration tests | 🟡 Medium | Medium |

## Workflow

### 1. Understand the Gap
- Read the relevant source files before touching anything
- Identify all files that need to change
- Check if any other gaps depend on or interact with this one

### 2. Brainstorm Approaches
Propose 2–3 implementation approaches with trade-offs. Example for Gap #2 (rate limiting):
- **Option A**: `slowapi` middleware — fast, minimal code, library dependency
- **Option B**: Redis-based counter in route handler — no extra library, more control
- **Option C**: Nginx rate limiting — zero Python code, but infra change

### 3. Plan Changes
List every file that will be modified and what changes are needed.

### 4. Implement

Follow the relevant skills:
- New API endpoint → use `/add-api-endpoint`
- New Celery task → use `/add-celery-task`
- New DB columns → use `/add-db-migration`
- New tests → use `/write-tests`

### 5. Verify
- Run `make test` to ensure no regressions
- Test the specific feature manually
- Check `make lint` passes

## Gap-Specific Implementation Notes

### Gap #2 — Rate Limiting (slowapi)
```python
# backend/app/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# On the upload route:
@router.post("/upload")
@limiter.limit("5/hour")
async def upload_video(request: Request, ...):
```
Add `slowapi` to `requirements.txt`.

### Gap #4 — Temp File Cleanup
Add a cleanup step at end of Stage 5 in `pipeline.py`:
```python
# Clean up extracted audio and frame files
for pattern in [f"/tmp/audio_{video.id}*.wav", f"/tmp/frames_{video.id}*"]:
    for f in Path("/tmp").glob(f"audio_{video.id}*.wav"):
        f.unlink(missing_ok=True)
```
Or add a Celery beat task `cleanup_temp_files` that runs hourly.

### Gap #5 — Bulk Race Condition
In `backend/app/api/routes/clips.py`, the bulk review endpoint:
```python
# Wrap in explicit transaction with row lock
async with db.begin():
    stmt = select(Clip).where(Clip.id.in_(clip_ids), Clip.user_id == user_id).with_for_update()
    result = await db.execute(stmt)
    clips = result.scalars().all()
    for clip in clips:
        clip.review_status = action
```

### Gap #7 — Retry UI
Backend: Add `POST /videos/{id}/retry` route that:
1. Checks `video.status == "failed"`
2. Resets `video.status = "processing"` and `video.error = None`
3. Re-queues `process_video_pipeline.delay(str(video.id))`

Frontend: Add "Retry" button in `/videos/[id]/page.tsx` when `video.status === "failed"`.

### Gap #8 — Zod Form Validation
```typescript
// frontend/src/app/(main)/publish/[clipId]/page.tsx
import { z } from "zod"
const publishSchema = z.object({
  title: z.string().min(1, "Title required").max(100, "Max 100 chars"),
  description: z.string().max(5000, "Max 5000 chars").optional(),
  tags: z.array(z.string()).max(500, "Too many tags"),
})
```
