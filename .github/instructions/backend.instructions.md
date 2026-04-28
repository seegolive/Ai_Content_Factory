---
applyTo: "ai-content-factory/backend/**"
description: "Backend patterns for FastAPI routes, services, and Celery tasks in this project"
---

# Backend Development Patterns

## Adding a New API Route

1. Create handler in `backend/app/api/routes/<domain>.py`
2. Register router in `backend/app/main.py`
3. Add Pydantic request/response schemas in `backend/app/schemas/<domain>.py`
4. Business logic goes in `backend/app/services/<domain>.py` — never inline in routes

**Route template:**
```python
@router.get("/{id}", response_model=DomainResponse)
async def get_domain(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await domain_service.get_by_id(db, id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return result
```

## Database Queries

Always use explicit column selection, never SELECT *:
```python
stmt = select(Video.id, Video.title, Video.status).where(
    Video.user_id == user_id
).limit(50)
result = await db.execute(stmt)
```

For updates: commit only on success, session handles rollback via `async with db.begin()`.

## Adding a New Celery Task

- Place in `backend/app/workers/tasks/`
- Bind with `bind=True` for retry access
- Check idempotency at the top (skip if already done)
- Route to correct queue in `celery_app.py` task_routes
- Handle `SoftTimeLimitExceeded` from `celery.exceptions`

## Service Pattern

Services are pure async functions (no class required for simple cases):
```python
# backend/app/services/my_service.py
async def process_item(db: AsyncSession, item_id: uuid.UUID) -> ItemResult:
    ...
```

For stateful services (e.g., ML models), use module-level singletons with lazy initialization.

## Known Stubs (DO NOT fill in without understanding pipeline.py first)

- `workers/tasks/transcribe.py` — intentional `pass`, pipeline.py handles Stage 1 inline
- `workers/tasks/analyze.py` — intentional `pass`, pipeline.py handles Stage 2 inline  
- `workers/tasks/process_video.py` — intentional `pass`, pipeline.py handles Stage 4 inline

## Critical Missing: game_detector.py

`backend/app/services/game_detector.py` does not exist yet. When building it:
- Use OpenCV for frame sampling (every N seconds)
- Extract game title text via OCR or classification
- Return `GameDetectionResult(game_title: str, confidence: float)`
- Called during Stage 2 (AI scoring) in `pipeline.py`
