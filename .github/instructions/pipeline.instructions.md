---
applyTo: "ai-content-factory/backend/app/workers/**"
description: "Checkpoint-resumable pipeline patterns for Celery workers in this project"
---

# Pipeline & Checkpoint System

## How the Checkpoint System Works

Each video has a `checkpoint` field (string enum). Before running any stage, check if it's already been completed:

```python
CHECKPOINTS = ["input_validated", "transcript_done", "ai_done", "qc_done", "clips_done", "review_ready"]

def _checkpoint_index(cp: str) -> int:
    return CHECKPOINTS.index(cp) if cp in CHECKPOINTS else -1
```

**Pattern for each stage:**
```python
if _checkpoint_index(video.checkpoint) >= _checkpoint_index("transcript_done"):
    logger.info(f"[Pipeline] Skipping transcription — already done for {video_id}")
else:
    # do the work
    video.checkpoint = "transcript_done"
    await db.commit()
```

## Stage Map

| Stage | Checkpoint set | What happens |
|-------|---------------|--------------|
| 0 | `input_validated` | MIME check, file size, ACRCloud copyright |
| 1 | `transcript_done` | faster-whisper GPU, saves to `video.transcript` |
| 2 | `ai_done` | AIBrain viral scoring, creates Clip rows |
| 3 | `qc_done` | VideoProcessor quality gate (resolution, bitrate) |
| 4 | `clips_done` | FFmpeg cuts + subtitle burn-in |
| 5 | `review_ready` | NotificationService (Telegram/SendGrid) |

## Retry Safety Rules

1. Any network call (Whisper, OpenRouter, YouTube) must have try/except + `self.retry(exc=e, countdown=60 * 2**self.request.retries)`
2. File operations must be idempotent — check if output file exists before recreating
3. DB writes must be wrapped in transaction — never partial commits across stages
4. On `SoftTimeLimitExceeded`: log progress, update `video.status = "failed"`, re-raise

## Adding a New Pipeline Stage

1. Add new checkpoint string to `CHECKPOINTS` list (in correct order)
2. Create Alembic migration if adding new DB columns for the stage
3. Add stage logic in `pipeline.py` after the previous stage block
4. Stage must: check checkpoint first → do work → set checkpoint → commit → log
5. Update Section 11 in `copilot-instructions.md` with the new stage

## Beat Schedule (analytics.py tasks)

```
daily 06:00 WIB  → sync_channel_analytics
monday 07:00 WIB → generate_weekly_insight_report
```

Queues: `pipeline` (GPU tasks), `distribute` (YouTube), `analytics` (light tasks).
