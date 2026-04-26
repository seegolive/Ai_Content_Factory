# 🏭 AI Content Factory

![Python](https://img.shields.io/badge/Python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![Next.js](https://img.shields.io/badge/Next.js-15-black) ![Status](https://img.shields.io/badge/Status-MVP-orange)

> Automated video-to-clips pipeline: upload a long video → AI transcribes, scores virality, cuts clips, QC checks, and queues for review & YouTube publishing.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AI Content Factory                       │
│                                                             │
│  Next.js 15 Frontend (port 3000)                           │
│    └── Dashboard / Videos / Review Queue                   │
│         │                                                   │
│  FastAPI Backend (port 8000)                               │
│    ├── /api/v1/auth     (Google OAuth + JWT)               │
│    ├── /api/v1/videos   (upload, status, list)             │
│    └── /api/v1/clips    (review, bulk, publish)            │
│         │                                                   │
│  Celery Workers (GPU-enabled)                              │
│    └── Pipeline: validate → transcribe → AI → QC → cut    │
│         │                                                   │
│  ┌──────┴──────┐                                           │
│  │  PostgreSQL │  Redis (broker + cache)                   │
│  └─────────────┘                                           │
│                                                             │
│  External: Whisper (local GPU) · OpenRouter · ACRCloud     │
│            YouTube Data API · Telegram · SendGrid          │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Node.js** 20+
- **Python** 3.12+
- **Docker** + Docker Compose
- **NVIDIA GPU** (RTX 4070 12GB recommended) + drivers
- **CUDA** 12.4
- **FFmpeg** (installed in Docker image)

---

## Quick Start (5 steps)

```bash
# 1. Clone and enter project
cd ai-content-factory

# 2. Copy env and configure
cp .env.example .env
# Edit .env — fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OPENROUTER_API_KEY

# 3. Start all services
make dev

# 4. Run database migrations
make migrate

# 5. Open browser
open http://localhost:3000
```

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `GOOGLE_CLIENT_ID` | Google OAuth App client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth App client secret |
| `OPENROUTER_API_KEY` | OpenRouter API key (AI analysis) |
| `WHISPER_MODEL` | `large-v3` (default, best quality) |
| `WHISPER_DEVICE` | `cuda` for GPU, `cpu` fallback |
| `ACRCLOUD_*` | ACRCloud credentials for copyright check |
| `TELEGRAM_BOT_TOKEN` | Telegram bot for notifications |

---

## Development Guide

### Start local dev stack
```bash
make dev           # Start all Docker containers
make logs          # Tail all logs
make logs-worker   # Tail Celery worker only
```

### Test the pipeline with a sample video
```bash
# 1. Login to frontend at http://localhost:3000
# 2. Go to Videos page
# 3. Upload an MP4 file or paste a YouTube URL
# 4. Watch processing progress in Dashboard
# 5. Review clips in Review Queue (keyboard: A=approve, R=reject, J/K=navigate)
```

### Monitor Celery
```bash
make flower        # Opens Flower at http://localhost:5555
make redis-cli     # Redis CLI for debugging queues
```

### Database operations
```bash
make migrate                 # Apply migrations
make makemigrations          # Create new migration
make shell-db                # psql into database
```

---

## API Documentation

Swagger UI available at: `http://localhost:8000/docs`

ReDoc: `http://localhost:8000/redoc`

---

## Pipeline Stages

| Stage | Checkpoint | Description |
|---|---|---|
| 1 | `input_validated` | File check + ACRCloud copyright pre-scan |
| 2 | `transcript_done` | Whisper large-v3 transcription (GPU) |
| 3 | `ai_done` | OpenRouter AI viral scoring + clip suggestions |
| 4 | `qc_done` | Quality control gate |
| 5 | `clips_done` | FFmpeg cut + resize + subtitle burn |
| 6 | `review_ready` | Notification sent, clips ready for review |

Pipeline is **checkpoint-resumable** — if a stage fails, retry picks up where it left off.

---

## GPU Setup (Windows WSL2 CUDA)

```bash
# 1. Install NVIDIA drivers for Windows (not WSL)
# 2. Install CUDA toolkit in WSL2:
sudo apt-get install -y nvidia-cuda-toolkit

# 3. Verify GPU is accessible:
nvidia-smi

# 4. Docker GPU access is configured in docker-compose.yml
#    celery_worker service has: deploy.resources.reservations.devices
```

---

## Troubleshooting

**Whisper falls back to CPU**: CUDA not available in container. Check `nvidia-smi` inside container:
```bash
docker compose exec celery_worker nvidia-smi
```

**Database connection refused**: Wait for postgres healthcheck to pass, or run `make dev` again.

**OpenRouter returns errors**: Verify `OPENROUTER_API_KEY` in `.env`. Check `make logs-worker` for error details.

**YouTube upload fails**: Ensure OAuth scope includes `youtube.upload`. Re-authenticate via `/auth/google/login`.

---

## Roadmap

| Version | Features |
|---|---|
| **V1 (MVP)** | Upload, transcribe, AI clip detection, review queue, YouTube publish |
| **V2** | SDXL thumbnail generation, multi-channel support, brand kits |
| **V3** | TikTok/Instagram/Reels distribution, analytics dashboard |
| **V4** | SaaS multi-tenant, billing, team collaboration |

---

*Built for local execution on Ryzen 9800X3D + RTX 4070 · Target: 10 beta users, 100 clips/week*
