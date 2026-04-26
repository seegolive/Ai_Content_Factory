# AI Content Factory MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full-stack AI Content Factory that automates video-to-clips pipeline with Whisper transcription, AI analysis, FFmpeg processing, and YouTube distribution.

**Architecture:** FastAPI async backend + Celery workers (GPU-enabled) + Next.js 15 frontend + PostgreSQL + Redis. Pipeline is checkpoint-based and resumable.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Celery, faster-whisper, OpenRouter, FFmpeg, Next.js 15, TailwindCSS v4, shadcn/ui, Zustand, TanStack Query.

---

## PHASE 1 — Project Scaffold

### Task 1: Create directory structure
- [ ] Create `ai-content-factory/` with all subdirs (backend + frontend tree from spec)
- [ ] Create empty `__init__.py` files for all Python packages
- [ ] Create placeholder `.tsx` files for frontend

### Task 2: docker-compose.yml + .env.example
- [ ] Write `docker-compose.yml` (postgres, redis, backend, celery_worker, flower, frontend)
- [ ] Write `.env.example` with all vars from spec
- [ ] Write `Makefile` with all commands

---

## PHASE 2 — Backend Core

### Task 3: Config + Database
- [ ] `backend/app/core/config.py` — Pydantic BaseSettings
- [ ] `backend/app/core/database.py` — AsyncEngine, SessionLocal, get_db, init_db

### Task 4: SQLAlchemy Models
- [ ] `backend/app/models/user.py`
- [ ] `backend/app/models/video.py` (YoutubeAccount + Video)
- [ ] `backend/app/models/clip.py`
- [ ] `backend/app/models/brand_kit.py`

### Task 5: Schemas + Security
- [ ] `backend/app/schemas/user.py`, `video.py`, `clip.py`
- [ ] `backend/app/core/security.py` — JWT, OAuth helpers

### Task 6: FastAPI main app + Auth API
- [ ] `backend/app/main.py` — CORS, lifespan, routers, health
- [ ] `backend/app/api/routes/auth.py` — Google OAuth endpoints

### Task 7: Videos + Clips API
- [ ] `backend/app/api/routes/videos.py`
- [ ] `backend/app/api/routes/clips.py`
- [ ] `backend/app/api/dependencies.py`

---

## PHASE 3 — Core Services

### Task 8: Transcription Service
- [ ] `backend/app/services/transcription.py` — faster-whisper, CUDA, thread pool

### Task 9: AI Brain Service
- [ ] `backend/app/services/ai_brain.py` — OpenRouter, viral scoring, JSON output

### Task 10: Video Processor Service
- [ ] `backend/app/services/video_processor.py` — FFmpeg cut/resize/subtitle/QC

### Task 11: Support Services
- [ ] `backend/app/services/copyright_check.py` — ACRCloud
- [ ] `backend/app/services/notification.py` — Telegram + SendGrid
- [ ] `backend/app/services/youtube_service.py` — YouTube Data API v3

---

## PHASE 4 — Celery Pipeline

### Task 12: Celery App + Pipeline
- [ ] `backend/app/workers/celery_app.py`
- [ ] `backend/app/workers/tasks/pipeline.py` — checkpoint orchestrator
- [ ] `backend/app/workers/tasks/transcribe.py`, `analyze.py`, `process_video.py`, `distribute.py`

---

## PHASE 5 — Frontend

### Task 13: Next.js setup + design system
- [ ] `frontend/package.json`, `tailwind.config.ts`, `next.config.ts`
- [ ] Global CSS with design tokens (colors, fonts)
- [ ] `frontend/src/types/index.ts`

### Task 14: Layout components
- [ ] `Sidebar.tsx`, `Header.tsx`, `StatusBar.tsx`
- [ ] `frontend/src/app/dashboard/layout.tsx`

### Task 15: Pages
- [ ] Dashboard home (`dashboard/page.tsx`)
- [ ] Videos page + VideoUploader + VideoCard
- [ ] Video detail `videos/[id]/page.tsx`
- [ ] Review Queue `review/page.tsx` + ClipPlayer + BulkActions

### Task 16: API layer + stores
- [ ] `lib/api.ts` — Axios + interceptors + type-safe functions
- [ ] `stores/videoStore.ts`, `stores/uiStore.ts`
- [ ] TanStack Query hooks

---

## PHASE 6 — Finalization

### Task 17: Backend requirements.txt + Dockerfile
### Task 18: Frontend Dockerfile
### Task 19: Alembic migration
### Task 20: README.md
### Task 21: Basic tests (conftest, test_videos, test_ai_brain)
