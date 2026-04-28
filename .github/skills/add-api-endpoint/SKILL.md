---
name: add-api-endpoint
description: "Add a new FastAPI endpoint to this project. Use when: creating new routes, adding CRUD operations, building new API features, implementing new backend functionality. Covers route handler, Pydantic schema, service function, and test."
argument-hint: "e.g. 'GET /videos/{id}/transcript' or 'POST /notifications/mark-read'"
---

# Add New API Endpoint

## When to Use
- Adding a new route to any of the route files in `backend/app/api/routes/`
- Creating a new resource domain (new route file + service)
- Implementing endpoints listed in Known Gaps in `copilot-instructions.md`

## Procedure

### 1. Read Context First
- Read the existing route file for the domain (e.g., `backend/app/api/routes/clips.py`)
- Read the related schema file (`backend/app/schemas/`)
- Read `backend/app/api/dependencies.py` for available dependencies

### 2. Add Pydantic Schema (if needed)
File: `backend/app/schemas/<domain>.py`
```python
class MyActionRequest(BaseModel):
    field: str
    optional_field: int | None = None

class MyActionResponse(BaseModel):
    id: uuid.UUID
    result: str
    model_config = ConfigDict(from_attributes=True)
```

### 3. Add Service Function
File: `backend/app/services/<domain>_service.py`
```python
async def my_action(
    db: AsyncSession,
    resource_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MyActionRequest,
) -> MyActionResponse:
    # 1. Fetch resource, verify ownership
    stmt = select(MyModel).where(MyModel.id == resource_id, MyModel.user_id == user_id)
    result = await db.execute(stmt)
    resource = result.scalar_one_or_none()
    if not resource:
        raise ValueError("Not found or access denied")
    # 2. Do work
    # 3. Commit
    await db.commit()
    await db.refresh(resource)
    return resource
```

### 4. Add Route Handler
File: `backend/app/api/routes/<domain>.py`
```python
@router.post("/{id}/action", response_model=MyActionResponse, status_code=200)
async def my_action_endpoint(
    id: uuid.UUID,
    payload: MyActionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await my_service.my_action(db, id, current_user.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

**HTTP status rules:**
- `200` — synchronous result returned
- `201` — resource created
- `202` — async task queued (returns `{"task_id": "..."}`)
- `400` — invalid input
- `404` — resource not found / not owned by user
- `403` — authenticated but forbidden

### 5. Register Router (new domains only)
File: `backend/app/main.py` — add `app.include_router(...)` under the existing block.

### 6. Write the Test
File: `backend/tests/test_api/test_<domain>.py`
- Follow the pattern in `backend/tests/test_api/test_clips.py`
- Use the `client` and `auth_headers` fixtures from `conftest.py`
- Test: success case, 404 case, unauthorized (no token)

## Checklist
- [ ] Schema has `model_config = ConfigDict(from_attributes=True)` if mapped to ORM
- [ ] Route uses `Depends(get_current_user)` — never skip auth
- [ ] Service checks `user_id` ownership — never trust ID alone
- [ ] New env vars added to `backend/.env.example` if needed
- [ ] No `print()` or debug statements

## Reference Files
- [dependencies.py](../../ai-content-factory/backend/app/api/dependencies.py)
- [routes/clips.py](../../ai-content-factory/backend/app/api/routes/clips.py) — best example of full CRUD
- [schemas/clip.py](../../ai-content-factory/backend/app/schemas/clip.py)
