---
name: add-celery-task
description: "Add a new Celery task or pipeline stage to this project. Use when: creating new background jobs, adding pipeline stages, adding beat schedule tasks, implementing async processing. Covers task definition, queue routing, idempotency, retry logic, and checkpoint integration."
argument-hint: "e.g. 'cleanup temp files beat task' or 'new pipeline stage for thumbnail generation'"
---

# Add New Celery Task

## When to Use
- Adding a new background job (not part of main pipeline)
- Adding a new stage to the 6-stage pipeline in `pipeline.py`
- Adding a recurring beat schedule task
- Implementing deferred work items from Known Gaps

## Read First
- [pipeline.py](../../ai-content-factory/backend/app/workers/tasks/pipeline.py) — understand checkpoint system before touching the pipeline
- [celery_app.py](../../ai-content-factory/backend/app/workers/celery_app.py) — queues, routes, beat schedule

## Procedure

### Option A: Standalone Background Task (not in pipeline)

1. **Create or add to** `backend/app/workers/tasks/<domain>.py`:

```python
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name="tasks.my_task",
    queue="pipeline",           # choose: pipeline / distribute / analytics
    max_retries=3,
    soft_time_limit=300,        # seconds before SoftTimeLimitExceeded
    time_limit=360,
)
def my_task(self, resource_id: str) -> dict:
    """Brief description of what this does."""
    logger.info(f"[MyTask] Starting for resource_id={resource_id}")
    try:
        # Check idempotency — skip if already done
        # Do work
        # Return result dict (JSON-serializable)
        return {"status": "done", "resource_id": resource_id}
    except SoftTimeLimitExceeded:
        logger.error(f"[MyTask] Soft time limit exceeded for {resource_id}")
        raise
    except Exception as e:
        logger.error(f"[MyTask] Failed: {e}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

2. **Register queue routing** in `celery_app.py`:
```python
task_routes = {
    ...
    "tasks.my_task": {"queue": "pipeline"},
}
```

3. **If it's a beat (scheduled) task**, add to `beat_schedule`:
```python
beat_schedule = {
    ...
    "my-task-daily": {
        "task": "tasks.my_task",
        "schedule": crontab(hour=6, minute=0),  # WIB = UTC+7, so UTC 23:00
        "args": [],
    },
}
```

### Option B: New Pipeline Stage (modifies pipeline.py)

**READ `pipeline.instructions.md` first.** Then:

1. Add checkpoint string to `CHECKPOINTS` list in correct order
2. Create Alembic migration if new DB columns needed (`make makemigrations`)
3. Add stage block in `pipeline.py` after the previous stage:

```python
# ── Stage N: My New Stage ──────────────────────────────────────────────────
if _checkpoint_index(video.checkpoint) < _checkpoint_index("my_stage_done"):
    logger.info(f"[Pipeline] Stage N: my_stage for video_id={video.id}")
    try:
        # do work
        video.checkpoint = "my_stage_done"
        await db.commit()
    except Exception as e:
        video.status = "failed"
        video.error = str(e)
        await db.commit()
        raise
else:
    logger.info(f"[Pipeline] Skipping Stage N — checkpoint already past")
```

4. Update Section 11 in `.github/copilot-instructions.md` with the new stage.

## Idempotency Rules
- For file operations: check if output file exists before recreating
- For DB inserts: use `INSERT ... ON CONFLICT DO NOTHING` or check first
- For API calls (YouTube, Groq): check if result already stored in DB
- Never rely on task ID as uniqueness — task can be re-queued with same args

## Celery Queues
| Queue | Workers | Use for |
|-------|---------|---------|
| `pipeline` | GPU worker (concurrency=2) | Whisper, FFmpeg, AI scoring |
| `distribute` | CPU worker | YouTube upload, notifications |
| `analytics` | CPU worker | YouTube Data API, insight generation |

## Test Your Task
```bash
# In backend container shell
make shell-backend
from app.workers.tasks.my_module import my_task
my_task.apply(args=["test-id"]).get(timeout=30)  # synchronous test
```
