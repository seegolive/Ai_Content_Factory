---
name: add-db-migration
description: "Add an Alembic database migration for this project. Use when: adding new columns, creating new tables, changing column types, adding indexes, or altering constraints. Covers SQLAlchemy model update, migration file creation, and forward/backward compatibility."
argument-hint: "e.g. 'add retry_count column to videos' or 'create notifications table'"
---

# Add Database Migration

## When to Use
- Adding new columns to existing models
- Creating new SQLAlchemy models with tables
- Adding or removing indexes
- Altering column types or nullability
- Implementing features from Known Gaps that require schema changes

## Read First
- Look at an existing migration for style: [003_add_v2_fields.py](../../ai-content-factory/backend/alembic/versions/003_add_v2_fields.py)
- Check the current model: `backend/app/models/<model>.py`
- **Never** run migrations on production without testing on dev first

## Procedure

### 1. Update the SQLAlchemy Model

File: `backend/app/models/<model>.py`

```python
# Add new column
new_field: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

# Add new column with index
channel_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

# Add JSONB column
metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

**Important:** `nullable=True` for any new column added to an existing populated table — never add `NOT NULL` without a default on existing tables.

### 2. Generate Migration File

```bash
make makemigrations
# or manually:
docker compose exec backend alembic revision --autogenerate -m "add_my_field_to_videos"
```

This creates `backend/alembic/versions/00N_add_my_field_to_videos.py`.

### 3. Edit Generated Migration

Verify the auto-generated file — Alembic sometimes misses:
- `server_default` for new NOT NULL columns
- Dropping indexes that were renamed
- JSONB type imports

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB  # if needed

def upgrade() -> None:
    op.add_column(
        "videos",
        sa.Column("retry_count", sa.Integer(), nullable=True, server_default="0"),
    )
    # Add index if needed:
    op.create_index("ix_videos_retry_count", "videos", ["retry_count"])

def downgrade() -> None:
    op.drop_index("ix_videos_retry_count", table_name="videos")
    op.drop_column("videos", "retry_count")
```

### 4. Apply Migration

```bash
make migrate
# or:
docker compose exec backend alembic upgrade head
```

### 5. Verify

```bash
make shell-db
\d videos  # check column exists in psql
```

## Naming Convention
Migration files follow: `00N_<description_snake_case>.py`
Next number = current highest + 1. Check `backend/alembic/versions/` first.

## Common Patterns

### New Table
```python
def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(100), nullable=False, index=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
```

### Add Index on Existing Column
```python
def upgrade() -> None:
    op.create_index("ix_clips_viral_score", "clips", ["viral_score"])

def downgrade() -> None:
    op.drop_index("ix_clips_viral_score", table_name="clips")
```

### Rename Column (safe two-step)
```python
# Step 1 migration: add new column, backfill
# Step 2 migration: drop old column
# Never rename in a single migration on live data
```

## Safety Rules
- Always implement `downgrade()` — rollback must work
- Test with `alembic downgrade -1` then `alembic upgrade head` before committing
- New NOT NULL columns require `server_default` or migration-time data backfill
- Avoid long-running locks: use `op.execute("SET lock_timeout = '2s'")` before `ALTER TABLE` on large tables
