# AI Content Factory — Copilot & Agent Instructions

> These instructions apply to all AI agents working in this repository:
> GitHub Copilot, Claude Code, Cursor, Windsurf, and any LLM-based assistant.

---

## Project Overview

**AI Content Factory** is a full-stack automated video-to-clips pipeline:
- Upload long video → AI transcribes → scores virality → cuts clips → QC → review queue → YouTube publish
- Stack: FastAPI (Python 3.12) + Next.js 15 + Celery + PostgreSQL + Redis
- GPU: NVIDIA RTX 4070 12GB (faster-whisper CUDA, FFmpeg)
- AI: OpenRouter (Claude Sonnet) for viral scoring

---

## 1. Brainstorming (before any implementation)

**ALWAYS explore before building.**

Before implementing any feature, modification, or component:
1. Understand the current project state (read relevant files first)
2. Ask ONE clarifying question at a time
3. Propose 2–3 approaches with trade-offs
4. Present your recommended approach with reasoning
5. Get confirmation before writing code

Do NOT jump straight to implementation. Clarify purpose, constraints, and success criteria first.

---

## 2. Senior Architect Principles

**Apply to all architectural decisions.**

- Design for scalability, maintainability, and observability from day one
- Use async-first patterns (FastAPI async, SQLAlchemy async, Celery)
- All pipeline stages must be **idempotent** and **checkpoint-resumable**
- Separate concerns: API layer → service layer → worker layer → data layer
- Use dependency injection (FastAPI `Depends`) — never import services directly in routes
- Document architecture decisions with trade-offs in `docs/`
- Prefer composition over inheritance
- Design for failure: every external call (Whisper, OpenRouter, ACRCloud, YouTube) must have retry logic and fallback

**Tech decision defaults for this project:**
- API: FastAPI + Pydantic v2
- DB ORM: SQLAlchemy 2.0 async
- Migrations: Alembic
- Queue: Celery + Redis
- Container: Docker Compose with GPU passthrough
- Frontend: Next.js 15 App Router + TailwindCSS v4 + shadcn/ui

---

## 3. Senior Backend Principles

**Apply when writing FastAPI, Celery, database, or service code.**

### API Design
- All routes return typed Pydantic response models
- Use HTTP status codes correctly: 202 for async ops, 404 for not found, 400 for validation, 401/403 for auth
- Never expose internal IDs directly — use UUIDs
- Paginate all list endpoints
- Version all APIs under `/api/v1/`

### Database
- Use async SQLAlchemy sessions via `get_db` dependency
- Never use `.all()` without LIMIT on large tables
- Index foreign keys and frequently queried columns
- Use `select()` with explicit columns, not `SELECT *`
- Transactions: commit only on success, rollback on exception

### Celery Workers
- All tasks must be idempotent (safe to retry)
- Use checkpoint system: check `video.checkpoint_index` before each stage
- Log progress at each stage with structured logging
- Handle `SoftTimeLimitExceeded` gracefully
- Never block the main thread in async code — use `asyncio.get_event_loop().run_in_executor()` for sync operations

### Security
- Validate all user input at API boundaries
- Sanitize file paths — never use user-supplied filenames directly
- JWT tokens expire in 24h, use HTTPS only in production
- Never log secrets, tokens, or PII
- Rate limit upload endpoints

---

## 4. Senior Frontend Principles

**Apply when writing Next.js, React, or TypeScript code.**

### Component Architecture
- Use Next.js 15 App Router — all pages in `src/app/`
- Server Components by default, `"use client"` only when needed (interactivity, browser APIs)
- Co-locate component styles with the component file
- Keep components under 200 lines — extract sub-components if larger
- Props must be typed with TypeScript interfaces

### State Management
- Server state: TanStack Query (React Query) — no manual `useEffect` for data fetching
- Client state: Zustand stores in `src/stores/`
- Never store derived state — compute from source
- Optimistic updates for review actions (approve/reject clips)

### Performance
- Use `next/image` for all images
- Lazy load heavy components with `dynamic(() => import(...))`
- Memoize expensive computations with `useMemo`
- Avoid re-renders: stable references with `useCallback`
- Bundle: keep initial JS under 100KB gzipped

### Code Style
- TypeScript strict mode — no `any`
- Named exports only (no default exports except pages)
- Use `cn()` utility for conditional classNames
- Tailwind utility classes — no inline styles

---

## 5. UI Design System Principles

**Apply when building or modifying UI components.**

### Design Tokens (from tailwind.config.ts)
- Colors: use semantic tokens (`primary`, `secondary`, `destructive`, `muted`) not raw hex
- Spacing: 8pt grid system (multiples of 2/4/8/16/32)
- Typography: consistent scale (xs/sm/base/lg/xl/2xl/3xl)
- Shadows: use Tailwind shadow utilities, not custom CSS

### Component Standards
- All interactive elements must have focus states (`focus-visible:ring-2`)
- Minimum touch target: 44×44px for mobile
- Loading states: skeleton or spinner, never empty content flash
- Error states: inline error messages, not alerts
- Empty states: meaningful copy + CTA, not blank space

### Accessibility
- Semantic HTML (`button` not `div` for clickable elements)
- ARIA labels on icon-only buttons
- Keyboard navigation support (Tab, Enter, Escape)
- Color contrast ratio ≥ 4.5:1 for text

---

## 6. Senior Prompt Engineer Principles

**Apply when writing system prompts, AI calls, or modifying `ai_brain.py`.**

### Prompt Design
- Be explicit about output format — always request JSON with schema
- Include examples in few-shot prompts
- Chain-of-thought for complex reasoning: "Think step by step..."
- Constrain output length to avoid runaway generation
- Include negative examples: "Do NOT include..."

### OpenRouter / LLM Calls
- Always set `temperature` explicitly (0.3 for factual, 0.7 for creative)
- Set `max_tokens` to prevent runaway costs
- Parse and validate LLM JSON output — never trust raw string
- Retry on `429` / rate limit with exponential backoff
- Log `model_used` and `tokens_used` for every call
- Fallback to cheaper model if primary fails

### AI Brain Service (`ai_brain.py`)
- Viral scoring prompt must request scores 0–100 with reasoning
- Clip suggestions must include: `start_time`, `end_time`, `viral_score`, `titles[]`, `hook_text`, `hashtags[]`
- Sort clips by `viral_score` descending before returning
- Malformed JSON → return empty list, log warning, do NOT raise

---

## 7. Code Review Standards

**Apply before committing or submitting PRs.**

### Checklist
- [ ] No hardcoded secrets, API keys, or credentials
- [ ] All new endpoints have authentication (`get_current_user` dependency)
- [ ] Database queries use async session correctly
- [ ] Celery tasks are idempotent
- [ ] Frontend components have TypeScript types (no `any`)
- [ ] Error handling at all external API calls
- [ ] No `console.log` / `print()` debug statements left in
- [ ] Tests written for new service functions
- [ ] `.env.example` updated if new env vars added

### Anti-patterns to avoid
- `SELECT *` queries
- Blocking I/O in async functions
- `localStorage` for sensitive data (use httpOnly cookies for tokens in production)
- God components (one component doing everything)
- Magic numbers (use named constants)
- Swallowing exceptions silently

---

## 8. Security Principles

**Apply to all code touching auth, file handling, or external APIs.**

- **File uploads**: validate MIME type AND magic bytes, not just extension
- **Path traversal**: always use `pathlib.Path` and resolve against a safe base directory
- **SQL**: use SQLAlchemy ORM or parameterized queries — never string concatenation
- **Auth**: validate JWT on every protected request, check user ownership of resources
- **CORS**: whitelist specific origins, never `*` in production
- **Secrets**: load from env vars via `config.py` (Pydantic BaseSettings), never hardcode
- **Dependency injection**: use `get_current_user` on all protected routes

---

## 9. Git & Workflow

- Branch naming: `feat/`, `fix/`, `refactor/`, `chore/`
- Commit messages: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:` (Conventional Commits)
- Never commit `.env` files
- Never commit video files (`*.mp4`, `*.mkv`, etc.)
- PRs require passing tests (`make test`) before merge

---

## 10. Project File Structure

```
ai-content-factory/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # FastAPI route handlers
│   │   ├── core/            # config, database, security
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   └── workers/tasks/   # Celery tasks
│   ├── alembic/versions/    # DB migrations
│   └── tests/               # pytest test suite
├── frontend/
│   └── src/
│       ├── app/             # Next.js App Router pages
│       ├── components/      # Reusable UI components
│       ├── lib/             # API client, query hooks, utils
│       ├── stores/          # Zustand state
│       └── types/           # TypeScript type definitions
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## 11. Pipeline Stages (Checkpoint System)

| Index | Checkpoint | Task |
|---|---|---|
| 0 | `input_validated` | File check + ACRCloud copyright |
| 1 | `transcript_done` | Whisper large-v3 GPU transcription |
| 2 | `ai_done` | OpenRouter viral scoring |
| 3 | `qc_done` | Quality control gate |
| 4 | `clips_done` | FFmpeg cut + subtitle |
| 5 | `review_ready` | Notify, ready for review |

Each stage checks `video.checkpoint_index` before running — if already past that stage, skip it.

---

## Quick Commands

```bash
make dev          # Start all Docker services
make test         # Run pytest
make migrate      # Apply DB migrations
make logs-worker  # Tail Celery worker logs
make flower       # Celery monitor at :5555
```
