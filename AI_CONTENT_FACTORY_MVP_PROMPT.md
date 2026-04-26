# 🏭 AI CONTENT FACTORY — MVP Build Prompt
> Prompt ini dirancang untuk dijalankan menggunakan **Claude Sonnet** via **GitHub Copilot**
> Jalankan skills installation terlebih dahulu sebelum memulai sesi coding

---

## ⚡ STEP 0 — Install Skills & Plugins (Jalankan sekali di root project)

```bash
# Core Skills
npx claude-code-templates@latest --skill creative-design/frontend-design
npx claude-code-templates@latest --skill development/code-reviewer
npx claude-code-templates@latest --skill development/senior-frontend
npx claude-code-templates@latest --skill development/senior-backend
npx claude-code-templates@latest --skill development/skill-creator
npx claude-code-templates@latest --skill development/senior-architect
npx claude-code-templates@latest --skill creative-design/ui-ux-pro-max
npx claude-code-templates@latest --skill creative-design/ui-design-system
npx claude-code-templates@latest --skill development/brainstorming
npx claude-code-templates@latest --skill development/senior-fullstack
npx claude-code-templates@latest --skill development/senior-prompt-engineer

# Superpowers Plugin
npx claudepluginhub obra/superpowers --plugin superpowers
```

---

## 🧠 SYSTEM CONTEXT — Baca dulu sebelum eksekusi

Kamu adalah **Senior Fullstack Architect** yang membangun **AI Content Factory MVP** — sebuah platform produksi konten berbasis AI yang mengotomatisasi pipeline dari raw video hingga konten siap publish di YouTube.

**Spesifikasi hardware developer (local machine):**
- CPU: AMD Ryzen 9 9800X3D
- RAM: 32GB DDR5
- GPU: NVIDIA RTX 4070 (12GB VRAM)
- OS Target: Windows 11 / Ubuntu WSL2

**Prinsip pengembangan:**
- Gunakan skill `senior-architect` untuk semua keputusan arsitektur
- Gunakan skill `senior-backend` untuk FastAPI, Celery, dan database
- Gunakan skill `senior-frontend` + `frontend-design` + `ui-ux-pro-max` untuk semua UI
- Gunakan skill `code-reviewer` setiap setelah menulis modul baru
- Gunakan skill `senior-prompt-engineer` untuk semua system prompt AI
- **SELALU** tulis kode production-ready dengan error handling lengkap
- **SELALU** implementasikan checkpoint system di setiap stage pipeline

---

## 📦 STEP 1 — Project Initialization

### 1.1 Buat Struktur Direktori Project

```
Buat struktur project lengkap berikut dengan nama folder `ai-content-factory`:

ai-content-factory/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── videos.py
│   │   │   │   ├── clips.py
│   │   │   │   └── dashboard.py
│   │   │   └── dependencies.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── security.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── video.py
│   │   │   ├── clip.py
│   │   │   └── brand_kit.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── video.py
│   │   │   └── clip.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── transcription.py    # Whisper local
│   │   │   ├── ai_brain.py         # OpenRouter integration
│   │   │   ├── video_processor.py  # FFmpeg
│   │   │   ├── qc_service.py       # Quality Control
│   │   │   ├── copyright_check.py  # ACRCloud
│   │   │   ├── youtube_service.py  # YouTube API
│   │   │   └── notification.py     # Telegram + Email
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   └── tasks/
│   │   │       ├── __init__.py
│   │   │       ├── pipeline.py      # Main pipeline orchestrator
│   │   │       ├── transcribe.py
│   │   │       ├── analyze.py
│   │   │       ├── process_video.py
│   │   │       └── distribute.py
│   │   └── main.py
│   ├── alembic/
│   │   └── versions/
│   ├── tests/
│   │   ├── test_api/
│   │   ├── test_services/
│   │   └── conftest.py
│   ├── requirements.txt
│   ├── alembic.ini
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── login/
│   │   │   │   └── callback/
│   │   │   ├── dashboard/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── layout.tsx
│   │   │   │   └── components/
│   │   │   ├── videos/
│   │   │   │   ├── [id]/
│   │   │   │   │   └── page.tsx
│   │   │   │   └── page.tsx
│   │   │   ├── review/
│   │   │   │   └── page.tsx
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── ui/               # shadcn/ui components
│   │   │   ├── video/
│   │   │   │   ├── VideoUploader.tsx
│   │   │   │   ├── VideoCard.tsx
│   │   │   │   └── ProcessingStatus.tsx
│   │   │   ├── clips/
│   │   │   │   ├── ClipPlayer.tsx
│   │   │   │   ├── ClipCard.tsx
│   │   │   │   └── BulkActions.tsx
│   │   │   └── layout/
│   │   │       ├── Sidebar.tsx
│   │   │       ├── Header.tsx
│   │   │       └── StatusBar.tsx
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── auth.ts
│   │   │   └── utils.ts
│   │   ├── stores/
│   │   │   ├── videoStore.ts
│   │   │   └── uiStore.ts
│   │   └── types/
│   │       └── index.ts
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── Makefile
└── README.md
```

**Instruksi:** Buat semua file dan direktori di atas. Untuk file Python gunakan template kosong dengan docstring. Untuk file TypeScript gunakan template kosong dengan type exports.

---

### 1.2 Buat `docker-compose.yml`

```
Buat docker-compose.yml untuk local development dengan services:

1. postgres (image: postgres:16-alpine)
   - database: ai_content_factory
   - port: 5432
   - volume: postgres_data

2. redis (image: redis:7-alpine)
   - port: 6379
   - maxmemory: 2gb
   - maxmemory-policy: allkeys-lru

3. backend (build dari ./backend)
   - port: 8000
   - hot reload dengan volume mount
   - depends_on: postgres, redis
   - environment dari .env

4. celery_worker (build dari ./backend)
   - command: celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
   - GPU access: deploy resources reservations devices (nvidia)
   - depends_on: postgres, redis, backend

5. celery_flower (monitoring)
   - image: mher/flower
   - port: 5555
   - untuk monitor queue

6. frontend (build dari ./frontend)
   - port: 3000
   - hot reload

volumes: postgres_data, redis_data
networks: app_network (bridge)

PENTING: Tambahkan GPU access untuk celery_worker agar Whisper bisa pakai RTX 4070.
```

---

### 1.3 Buat `.env.example`

```
Buat .env.example lengkap dengan semua variabel environment:

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ai_content_factory
DATABASE_URL_SYNC=postgresql://postgres:password@localhost:5432/ai_content_factory

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Security
SECRET_KEY=your-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback

# YouTube API
YOUTUBE_API_KEY=

# OpenRouter
OPENROUTER_API_KEY=
OPENROUTER_MODEL=anthropic/claude-sonnet-4-5
OPENROUTER_FALLBACK_MODEL=openai/gpt-4o-mini

# Whisper Local
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

# ACRCloud (Copyright Check)
ACRCLOUD_HOST=
ACRCLOUD_ACCESS_KEY=
ACRCLOUD_ACCESS_SECRET=

# Telegram Bot
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# SendGrid
SENDGRID_API_KEY=
FROM_EMAIL=noreply@yourdomain.com

# Storage (Local untuk MVP)
STORAGE_TYPE=local
LOCAL_STORAGE_PATH=./storage
# Future: S3/R2
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET=
CLOUDFLARE_R2_ENDPOINT=

# App Config
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
FRONTEND_URL=http://localhost:3000
MAX_VIDEO_SIZE_GB=10
MAX_VIDEO_DURATION_HOURS=3
```

---

## 🗄️ STEP 2 — Database & Models

### 2.1 Setup Database dengan SQLAlchemy Async

```
Gunakan skill senior-backend.

Buat file backend/app/core/database.py:
- AsyncEngine dengan asyncpg
- AsyncSessionLocal factory
- Base declarative model
- get_db dependency untuk FastAPI
- Fungsi init_db() untuk create tables

Buat file backend/app/core/config.py:
- Pydantic BaseSettings
- Load dari .env file
- Validasi semua required fields
- Property computed untuk DATABASE_URL parsing
```

### 2.2 Buat Semua SQLAlchemy Models

```
Gunakan skill senior-backend dan senior-architect.

Buat models lengkap dengan relasi dan constraint yang tepat:

FILE: backend/app/models/user.py
- User model:
  - id: UUID PK
  - email: String(255) UNIQUE NOT NULL
  - google_id: String(255) UNIQUE NOT NULL  
  - name: String(255)
  - avatar_url: Text
  - plan: Enum('free', 'pro', 'agency') default 'free'
  - credits_used: Integer default 0
  - is_active: Boolean default True
  - created_at: DateTime with timezone
  - updated_at: DateTime with timezone (onupdate)
  - Relationship ke: youtube_accounts, videos

FILE: backend/app/models/video.py
- YoutubeAccount model:
  - id: UUID PK
  - user_id: UUID FK → users
  - channel_id: String(255) NOT NULL
  - channel_name: String(255)
  - access_token: Text (encrypted)
  - refresh_token: Text (encrypted)
  - token_expires_at: DateTime
  - content_dna: JSONB (default {})
  - created_at, updated_at

- Video model:
  - id: UUID PK
  - user_id: UUID FK → users
  - youtube_account_id: UUID FK → youtube_accounts (nullable)
  - title: String(500)
  - original_url: Text (YouTube URL atau local path)
  - file_path: Text (local storage path)
  - file_size_mb: Float
  - duration_seconds: Float
  - status: Enum('queued','processing','review','done','error') default 'queued'
  - checkpoint: String(100) (last successful stage)
  - error_message: Text
  - copyright_status: Enum('unchecked','clean','flagged') default 'unchecked'
  - transcript: Text
  - transcript_segments: JSONB (array of {start, end, text, speaker})
  - celery_task_id: String(255)
  - created_at, updated_at
  - Relationship ke: clips

FILE: backend/app/models/clip.py
- Clip model:
  - id: UUID PK
  - video_id: UUID FK → videos
  - user_id: UUID FK → users
  - title: Text
  - description: Text
  - start_time: Float NOT NULL
  - end_time: Float NOT NULL
  - duration: Float (computed)
  - viral_score: Integer (0-100)
  - hook_text: Text
  - hashtags: JSONB (array of strings)
  - thumbnail_path: Text
  - clip_path: Text
  - format: Enum('horizontal','vertical','square') default 'vertical'
  - qc_status: Enum('pending','passed','failed','manual_review') default 'pending'
  - qc_issues: JSONB (array of issue descriptions)
  - review_status: Enum('pending','approved','rejected') default 'pending'
  - reviewed_at: DateTime
  - platform_status: JSONB (default {})
  - speaker_id: String(100)
  - created_at, updated_at

FILE: backend/app/models/brand_kit.py  
- BrandKit model:
  - id: UUID PK
  - user_id: UUID FK → users
  - channel_id: String(255)
  - name: String(255)
  - primary_color: String(7)
  - accent_color: String(7)
  - logo_path: Text
  - font_primary: String(100)
  - sdxl_style_prompt: Text
  - is_active: Boolean default True
  - created_at, updated_at

PENTING: Semua model harus punya __tablename__, __repr__, dan indexes yang tepat untuk query performance.
```

### 2.3 Buat Alembic Migration

```
Buat initial Alembic migration yang membuat semua tabel.
Setup alembic.ini dengan DATABASE_URL dari environment.
Buat script migration: 001_initial_schema.py
```

---

## 🔧 STEP 3 — Backend API

### 3.1 FastAPI Main App

```
Gunakan skill senior-backend.

Buat backend/app/main.py:
- FastAPI app dengan metadata lengkap
- CORS middleware (allow origins dari config)
- Exception handlers (HTTPException, ValidationError, generic Exception)
- Lifespan context manager: init DB + setup storage directories
- Include semua routers dengan prefix /api/v1
- Health check endpoint GET /health yang return status + komponen
- Static files serving untuk /storage (local storage MVP)
- Request logging middleware
```

### 3.2 Authentication API

```
Gunakan skill senior-backend dan senior-architect.

Buat backend/app/api/routes/auth.py:

Endpoints:
1. GET /auth/google/login
   - Return Google OAuth URL
   - State parameter untuk CSRF protection
   
2. GET /auth/google/callback  
   - Exchange code untuk token
   - Get Google user info
   - Create atau update user di DB
   - Return JWT access token

3. GET /auth/me (protected)
   - Return current user profile
   - Include youtube_accounts

4. POST /auth/logout
   - Invalidate token (blacklist di Redis)

Buat backend/app/core/security.py:
- create_access_token(data, expires_delta)
- verify_token(token) → user_id
- get_current_user dependency
- Google OAuth flow helper

Gunakan python-jose untuk JWT, httpx untuk Google API calls.
```

### 3.3 Video Management API

```
Gunakan skill senior-backend.

Buat backend/app/api/routes/videos.py:

Endpoints:
1. POST /videos/upload
   - Accept multipart/form-data (video file)
   - Validasi: format, ukuran max 10GB, durasi max 3 jam
   - Save ke local storage
   - Create Video record di DB dengan status 'queued'
   - Trigger celery task: pipeline.process_video.delay(video_id)
   - Return: video_id, status, estimated_time
   
2. POST /videos/from-url
   - Accept: { youtube_url, youtube_account_id }
   - Validasi YouTube URL format
   - Create Video record
   - Trigger celery task
   - Return: video_id, status

3. GET /videos
   - List semua videos user (paginated)
   - Filter by status
   - Include clips count per video
   - Sorted by created_at DESC
   
4. GET /videos/{video_id}
   - Detail video dengan semua clips
   - Include processing progress per stage
   
5. DELETE /videos/{video_id}
   - Soft delete
   - Cancel celery task jika masih running
   - Cleanup files di storage

6. GET /videos/{video_id}/status
   - Real-time status polling endpoint
   - Return: stage, progress %, eta, error jika ada
   - Lightweight untuk frequent polling

Buat Pydantic schemas di backend/app/schemas/video.py untuk request/response.
```

### 3.4 Clips & Review API

```
Gunakan skill senior-backend.

Buat backend/app/api/routes/clips.py:

Endpoints:
1. GET /videos/{video_id}/clips
   - List clips untuk video tertentu
   - Filter: qc_status, review_status, viral_score_min
   - Sort: viral_score DESC (default), created_at

2. PATCH /clips/{clip_id}/review
   - Body: { action: 'approve' | 'reject', note?: string }
   - Update review_status dan reviewed_at
   - Jika approve: trigger publish jika ada platform yang dipilih

3. POST /clips/bulk-review
   - Body: { clip_ids: string[], action: 'approve' | 'reject' }
   - Bulk approve/reject dengan keyboard shortcut support

4. PATCH /clips/{clip_id}
   - Edit: title, description, hashtags (sebelum publish)
   
5. POST /clips/{clip_id}/publish
   - Body: { platforms: ['youtube'], youtube_account_id: string }
   - Trigger celery distribute task
   - Return: publish job id

6. GET /clips/{clip_id}/stream
   - Stream clip file untuk preview player
   - Support Range requests untuk seek
```

---

## ⚙️ STEP 4 — Core Services

### 4.1 Transcription Service (Whisper Local)

```
Gunakan skill senior-backend dan senior-prompt-engineer.

Buat backend/app/services/transcription.py:

Class WhisperTranscriptionService:

- __init__: 
  - Load faster-whisper model (large-v3)
  - Device: cuda, compute_type: float16 (optimal untuk RTX 4070)
  - Model caching: load sekali, reuse
  
- async transcribe(video_path: str, language: str = None) → TranscriptResult:
  - Run whisper dalam thread pool executor (biar tidak block event loop)
  - Output: 
    - full_text: str
    - segments: list of {id, start, end, text, confidence}
    - language: detected language
    - duration: float
  
- handle_errors:
  - CUDA OOM → fallback ke CPU dengan model medium
  - File not found → raise VideoNotFoundError
  - Log semua error dengan stack trace

TranscriptResult dataclass:
  - full_text: str
  - segments: List[TranscriptSegment]
  - language: str
  - duration: float
  - word_count: int

Requirements:
- faster-whisper (CTranslate2 backend)
- torch dengan CUDA support
- asyncio thread pool untuk non-blocking

CATATAN: faster-whisper jauh lebih efisien dari openai-whisper asli.
Dengan RTX 4070 12GB, large-v3 jalan di float16 = optimal.
```

### 4.2 AI Brain Service (OpenRouter)

```
Gunakan skill senior-backend dan senior-prompt-engineer.

Buat backend/app/services/ai_brain.py:

Class AIBrainService:

- __init__: Setup httpx async client untuk OpenRouter

- async analyze_transcript(transcript: TranscriptResult, channel_info: dict) → AIAnalysisResult:
  
  System prompt yang harus dibuat (gunakan skill senior-prompt-engineer):
  - Role: Expert viral content analyst
  - Task: Identify highlights, score virality, extract hooks
  - Output format: structured JSON
  - Context: transcript segments dengan timestamps
  - Optimization: viral scoring berdasarkan engagement signals
  
  Viral scoring criteria (0-100):
  - Emotional impact (0-25)
  - Information density (0-20)  
  - Hook strength pertama 5 detik (0-25)
  - Relatability & shareability (0-15)
  - Call-to-action potential (0-15)
  
  Output per clip:
  - start_time, end_time
  - viral_score
  - title (3 A/B variants)
  - hook_text
  - description (SEO-optimized)
  - hashtags (10-15 tags)
  - thumbnail_prompt (untuk SDXL - V2)
  - reason (why this clip is viral)

- async generate_titles(clip_info: dict) → List[str]:
  - Generate 3 title variants
  - Style: clickbait-but-honest, curiosity gap, how-to format

- _call_openrouter(messages, model, max_tokens) → str:
  - Retry logic: 3x dengan exponential backoff
  - Fallback: jika primary model gagal, gunakan fallback model
  - Rate limit handling
  - Response parsing dengan error handling

AIAnalysisResult dataclass:
  - clips: List[ClipSuggestion]
  - processing_time: float
  - model_used: str
  - tokens_used: int

PENTING: Semua prompt harus menghasilkan output JSON yang valid dan parseable.
Gunakan structured output / JSON mode jika tersedia di OpenRouter.
```

### 4.3 Video Processor Service (FFmpeg)

```
Gunakan skill senior-backend.

Buat backend/app/services/video_processor.py:

Class VideoProcessorService:

- async cut_clip(input_path, output_path, start_time, end_time) → str:
  - FFmpeg: -ss {start} -to {end} -c:v libx264 -c:a aac
  - Hardware acceleration: -hwaccel cuda -hwaccel_output_format cuda
  - Quality: -crf 23 -preset fast
  - Return output path

- async resize_for_platform(input_path, platform) → Dict[str, str]:
  - 'youtube': 1920x1080 (16:9) → output_horizontal.mp4
  - 'shorts': 1080x1920 (9:16) → output_vertical.mp4  
  - 'feed': 1080x1080 (1:1) → output_square.mp4
  - Smart cropping: detect face/action area, crop to center
  - Padding dengan blur background jika aspect ratio tidak pas

- async burn_subtitles(input_path, transcript_segments, style) → str:
  - Convert segments ke .srt format
  - Burn subtitle dengan ffmpeg -vf subtitles
  - Style: font size 48, bold, white dengan black outline
  - Positioning: bottom center

- async run_qc_check(clip_path) → QCResult:
  - Silence detection: ffmpeg silencedetect filter
    - Flag jika silence > 3 detik
  - Audio clipping: loudnorm analysis
    - Flag jika peak > -1dB
  - Blur frame: laplacian variance per frame sampling
    - Flag jika rata-rata variance < threshold
  - Black frame: blackdetect filter
  - Return: passed/failed + list of issues

- _run_ffmpeg(cmd: List[str]) → subprocess result:
  - asyncio subprocess
  - Timeout: 30 menit max
  - Capture stderr untuk error parsing
  - Raise VideoProcessingError jika returncode != 0

QCResult dataclass:
  - passed: bool
  - issues: List[QCIssue]
  - metrics: dict (silence_duration, peak_db, blur_score)
```

### 4.4 Copyright Check Service

```
Buat backend/app/services/copyright_check.py:

Class CopyrightCheckService:

- async check_audio(video_path: str) → CopyrightResult:
  - Extract 30 detik audio sample dari video
  - Send ke ACRCloud API
  - Parse response: music name, artist, label, status
  - Return: is_flagged, matched_content, confidence

- async extract_audio_sample(video_path, duration=30) → bytes:
  - FFmpeg: extract audio segment dari tengah video
  - Format: WAV 44100Hz mono

CopyrightResult dataclass:
  - is_flagged: bool
  - matched_music: Optional[str]
  - artist: Optional[str]
  - confidence: float
  - status: str ('clean', 'flagged', 'uncertain')
```

### 4.5 Notification Service

```
Buat backend/app/services/notification.py:

Class NotificationService:

- async send_telegram(message: str, parse_mode='HTML') → bool:
  - Send ke configured chat_id
  - Format pesan yang informatif dengan emoji
  - Retry 3x jika gagal

- async send_email(to: str, subject: str, body: str) → bool:
  - SendGrid API
  - HTML email template yang clean

- async notify_job_complete(video: Video, clips_count: int, user: User):
  - Format: "✅ Video '{title}' selesai diproses! {n} clips siap direview."
  - Kirim Telegram + Email

- async notify_job_error(video: Video, error: str, user: User):
  - Format: "❌ Error pada '{title}': {error}"
  
- async notify_upload_success(video: Video, platform: str, clip: Clip):
  - Format: "🚀 Clip '{title}' berhasil diupload ke {platform}!"
```

---

## 🚂 STEP 5 — Celery Pipeline (Core)

```
Gunakan skill senior-architect dan senior-backend.

Buat backend/app/workers/celery_app.py:
- Celery app dengan Redis broker
- Task serializer: json
- Result expiry: 7 hari
- Max retries: 3
- Beat schedule untuk analytics pull (future)

Buat backend/app/workers/tasks/pipeline.py — INI YANG PALING PENTING:

@celery_app.task(bind=True, max_retries=3)
def process_video_pipeline(self, video_id: str):
  """
  Main pipeline dengan checkpoint system.
  Setiap stage disimpan ke DB. Jika gagal, resume dari checkpoint terakhir.
  
  STAGES:
  1. input_validation   → validate file, copyright pre-check
  2. transcription      → Whisper local GPU
  3. ai_analysis        → OpenRouter: scoring, titles, hooks
  4. qc_filtering       → Auto QC per clip
  5. video_processing   → FFmpeg: cut, resize, subtitle
  6. review_ready       → Notify user untuk review
  
  Checkpoint flow:
  - Load video dari DB
  - Cek checkpoint terakhir
  - Skip stages yang sudah selesai
  - Jalankan stage berikutnya
  - Update checkpoint setelah setiap stage berhasil
  - Jika error: update status 'error', simpan error message, notify user
  """
  
  CHECKPOINT_ORDER = [
    'input_validated',
    'transcript_done', 
    'ai_done',
    'qc_done',
    'clips_done',
    'review_ready'
  ]
  
  # Implementasikan full pipeline dengan semua services
  # Setiap stage harus:
  # 1. Log awal stage
  # 2. Eksekusi service
  # 3. Save hasil ke DB
  # 4. Update checkpoint
  # 5. Handle error gracefully

PENTING: Pipeline harus idempotent. Jika dijalankan ulang dari checkpoint,
tidak boleh ada data duplikat atau side effects.
```

---

## 🎨 STEP 6 — Frontend Dashboard

### 6.1 Setup Next.js Project

```
Gunakan skill senior-frontend, ui-ux-pro-max, dan ui-design-system.

Setup Next.js 15 dengan:
- TypeScript strict mode
- TailwindCSS v4
- shadcn/ui (full install)
- Zustand untuk state management
- TanStack Query (React Query) untuk server state
- Axios untuk HTTP client
- Socket.io-client untuk real-time updates (polling fallback)

Design System yang harus diikuti:
- Color Palette: Dark theme dominant
  - Background: #0A0A0F (near black)
  - Surface: #13131A  
  - Border: #1E1E2E
  - Primary: #6C63FF (electric violet)
  - Secondary: #00D4AA (cyber teal)
  - Accent: #FF6B6B (coral)
  - Text Primary: #E8E8F0
  - Text Muted: #6B6B8A

- Typography:
  - Display: 'Space Grotesk' (headings)
  - Body: 'Inter' (body text)
  - Mono: 'JetBrains Mono' (code, metrics)

- Component style: glassmorphism dengan subtle borders
  - backdrop-blur, bg-opacity, ring effects
  - Smooth transitions 200ms ease
  - Hover states dengan subtle glow

PENTING: Dashboard harus terasa seperti pro-grade SaaS tool, bukan prototype.
```

### 6.2 Layout & Navigation

```
Gunakan skill frontend-design dan ui-ux-pro-max.

Buat frontend/src/components/layout/Sidebar.tsx:
- Fixed sidebar 240px
- Logo AI Content Factory di top
- Navigation items dengan icon:
  - Dashboard (overview stats)
  - Videos (upload & list)
  - Review Queue (clips pending review)
  - Analytics (coming soon - disabled)
  - Settings
- Bottom: user avatar + plan badge + logout
- Collapsible ke 64px (icon only) dengan smooth animation
- Active state: primary color dengan left border accent

Buat frontend/src/components/layout/Header.tsx:
- Breadcrumb navigation
- Right: notification bell + user menu
- Global search bar (untuk search videos/clips)
- Status bar: menampilkan active Celery jobs

Buat frontend/src/app/dashboard/layout.tsx:
- Sidebar + main content area
- Responsive: sidebar collapse di mobile
```

### 6.3 Dashboard Home Page

```
Gunakan skill frontend-design dan ui-ux-pro-max.

Buat frontend/src/app/dashboard/page.tsx:

Sections:
1. Stats Overview (top)
   - 4 metric cards: Total Videos, Clips Generated, Pending Review, Published
   - Trend indicator (up/down dari minggu lalu)
   - Glassmorphism card style dengan subtle glow

2. Active Processing Jobs
   - Real-time list videos yang sedang diproses
   - Progress bar per stage dengan label
   - Stage: Validated → Transcribing → Analyzing → QC → Processing → Ready
   - Cancel button
   - Auto-refresh setiap 3 detik via polling

3. Review Queue (Quick Access)
   - 5 clips dengan viral score tertinggi yang pending review
   - Thumbnail placeholder, title, score badge, approve/reject buttons
   - Link ke full review page

4. Recent Videos
   - List 5 video terbaru dengan status badge
   - Quick actions: view, reprocess, delete
```

### 6.4 Video Upload & Management Page

```
Gunakan skill frontend-design, senior-frontend.

Buat frontend/src/app/videos/page.tsx:

Sections:
1. Upload Section (prominent di top)
   - Drag & drop zone dengan animated border
   - File picker button
   - OR divider
   - YouTube URL input dengan paste button
   - Validasi real-time: format, size indicator
   - Upload progress bar dengan speed indicator
   - Submit button: "Start Processing"

2. Video Library
   - Grid/list toggle
   - Filter: All, Processing, Review, Done, Error
   - Sort: Newest, Oldest, Most Clips
   - VideoCard component per video:
     - Thumbnail (placeholder jika belum ada)
     - Title, duration, created date
     - Status badge (color-coded)
     - Pipeline progress indicator
     - Action menu: View Clips, Reprocess, Delete

Buat frontend/src/components/video/VideoUploader.tsx:
- Komponen upload standalone
- Drag & drop dengan visual feedback
- File validation sebelum upload
- Progress tracking via XHR dengan onUploadProgress
- Error state dengan retry option

Buat frontend/src/app/videos/[id]/page.tsx:
- Detail video dengan semua clips
- Video info header (title, duration, status, copyright status)
- Tabs: All Clips, Approved, Rejected, Pending
- Clips grid dengan ClipCard
```

### 6.5 Review Queue Page (PRIORITAS TINGGI)

```
Gunakan skill ui-ux-pro-max dan frontend-design.

Buat frontend/src/app/review/page.tsx:

Ini adalah halaman paling penting untuk UX — creator akan menghabiskan
banyak waktu di sini. Harus dibuat sangat efisien.

Layout:
- Split view: left = clip list, right = clip preview + detail
- Keyboard shortcuts (harus ada):
  - A = Approve clip yang sedang aktif
  - R = Reject
  - J/K = Navigate prev/next clip
  - Space = Play/pause preview
  - B = Bulk select

Left panel (clip list, 380px):
- Sorted by viral score DESC
- ClipCard mini: thumbnail, title, score badge, status
- Multi-select checkbox untuk bulk actions
- Bulk action bar muncul jika ada yang diselect

Right panel (main):
1. Video preview player (HTML5 video)
   - Custom controls yang clean
   - Subtitle overlay toggle
   - Loop clip button
   
2. Clip Info:
   - Editable title (click to edit inline)
   - Viral score dengan breakdown (tooltip hover)
   - Hook text
   - Hashtags (chips, editable)
   - Editable description

3. Action Bar (bottom, sticky):
   - Reject button (red) | Approve button (green, prominent)
   - Keyboard shortcut hints
   - Platform selector (checkboxes: YouTube, lebih banyak di V3)
   
4. QC Status indicator:
   - Issues list jika ada QC masalah
   - Warning badge jika score < 70

Buat frontend/src/components/clips/BulkActions.tsx:
- Floating action bar muncul saat ada selection
- Approve All, Reject All, Export List
```

### 6.6 API Integration Layer

```
Gunakan skill senior-frontend.

Buat frontend/src/lib/api.ts:
- Axios instance dengan baseURL dari env
- Request interceptor: inject JWT token dari localStorage
- Response interceptor: handle 401 (redirect login), 429 (rate limit toast)
- Type-safe API functions:
  - auth: login, logout, getMe
  - videos: list, upload, fromUrl, getById, getStatus, delete
  - clips: list, review, bulkReview, update, publish

Buat frontend/src/stores/videoStore.ts (Zustand):
- videos: Video[]
- activeVideoId: string | null
- processingJobs: Map<string, ProcessingStatus>
- actions: fetchVideos, uploadVideo, updateVideoStatus

Buat frontend/src/stores/uiStore.ts:
- sidebarCollapsed: boolean
- selectedClips: string[] (untuk bulk actions)
- reviewActiveClipId: string | null

Setup TanStack Query:
- QueryClient config: staleTime 30s, retry 2x
- Custom hooks:
  - useVideos()
  - useVideo(id)
  - useVideoStatus(id) — polling setiap 3 detik jika status 'processing'
  - useClips(videoId)
  - useMutations: useUploadVideo, useReviewClip, useBulkReview
```

---

## 🔑 STEP 7 — YouTube Integration

```
Gunakan skill senior-backend.

Buat backend/app/services/youtube_service.py:

Class YouTubeService:

- async upload_video(clip_path, title, description, tags, privacy='public') → str:
  - Google API Python client
  - Resumable upload untuk file besar
  - Return: youtube_video_id
  
- async get_channel_info(access_token) → ChannelInfo:
  - Channel ID, name, subscriber count, thumbnail
  
- async refresh_access_token(refresh_token) → str:
  - Refresh jika expired
  - Update di DB
  
- async check_upload_quota() → bool:
  - YouTube API quota: 10.000 units/day
  - Upload = 1600 units
  - Max ~6 uploads/day per account (free quota)
  - Warn user jika mendekati limit

CATATAN PENTING untuk MVP:
- YouTube Data API v3 quota sangat terbatas
- Untuk beta testing, gunakan 'unlisted' atau 'private' dulu
- Implementasikan quota tracking di DB
```

---

## ✅ STEP 8 — Requirements & Makefile

### 8.1 Backend Requirements

```
Buat backend/requirements.txt dengan versi yang spesifik:

# Web Framework
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-multipart==0.0.12

# Database
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
psycopg2-binary==2.9.10

# Redis & Celery
redis==5.2.0
celery[redis]==5.4.0
flower==2.0.1

# AI / ML
faster-whisper==1.1.0
torch==2.5.1+cu124  # CUDA 12.4 untuk RTX 4070
torchaudio==2.5.1+cu124

# HTTP Client
httpx==0.28.0
aiohttp==3.11.0

# Auth
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
google-auth==2.37.0
google-auth-oauthlib==1.2.1

# Google API
google-api-python-client==2.154.0

# Video Processing
ffmpeg-python==0.2.0

# Notification
python-telegram-bot==21.9
sendgrid==6.11.0

# Config & Utils
pydantic-settings==2.7.0
python-dotenv==1.0.1
loguru==0.7.3
tenacity==9.0.0

# Storage
boto3==1.35.0  # Future S3/R2

# Testing
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.28.0

CATATAN: torch harus install dengan CUDA index:
pip install torch==2.5.1+cu124 --index-url https://download.pytorch.org/whl/cu124
```

### 8.2 Makefile untuk Developer Experience

```
Buat Makefile di root project:

Commands:
- make setup         → Install semua dependencies, setup .env dari .env.example
- make dev           → Start docker-compose dev stack
- make down          → Stop semua containers
- make logs          → Tail logs semua services
- make logs-worker   → Tail hanya celery worker logs
- make migrate       → Jalankan alembic migrations
- make makemigrations → Buat migration baru (prompt nama)
- make shell-backend  → Exec bash ke backend container
- make shell-db      → Psql ke database
- make test          → Run pytest
- make lint          → Ruff + mypy
- make format        → Black + isort
- make redis-cli     → Redis CLI
- make flower        → Open Flower dashboard di browser
- make install-whisper → Download faster-whisper large-v3 model
- make clean         → Remove __pycache__, .pyc, tmp files

Tambahkan ASCII art header AI Content Factory di atas semua output.
```

---

## 📝 STEP 9 — README

```
Buat README.md yang komprehensif:

Sections:
1. Project Overview (dengan badge: Python, FastAPI, Next.js, status: MVP)
2. Architecture Diagram (ASCII art)
3. Prerequisites: Node 20+, Python 3.12+, Docker, NVIDIA GPU + drivers, CUDA 12.4
4. Quick Start (5 langkah)
5. Environment Variables (reference ke .env.example)
6. Development Guide:
   - Cara run local
   - Cara test pipeline dengan sample video
   - Cara akses Flower dashboard
7. API Documentation (reference ke /docs)
8. Pipeline Stages explanation
9. GPU Setup untuk Windows (WSL2 CUDA)
10. Troubleshooting common issues
11. Roadmap (V1 → V4)
```

---

## 🧪 STEP 10 — Testing & Validation

```
Gunakan skill code-reviewer dan senior-backend.

Buat tests minimal yang penting:

tests/test_services/test_transcription.py:
- Test WhisperTranscriptionService dengan sample audio file
- Test CUDA device detection
- Test fallback ke CPU

tests/test_services/test_ai_brain.py:
- Test prompt generation
- Test response parsing (mock OpenRouter)
- Test retry logic

tests/test_api/test_videos.py:
- Test upload endpoint (mock file)
- Test status endpoint
- Test auth protection

tests/conftest.py:
- Async test database setup
- Mock services fixtures
- Sample video fixture

Gunakan skill code-reviewer untuk review setiap test file.
```

---

## 🎯 EXECUTION ORDER

Jalankan dalam urutan ini, selesaikan satu sebelum lanjut ke berikutnya:

```
[ ] STEP 1.1 → Buat project structure
[ ] STEP 1.2 → docker-compose.yml  
[ ] STEP 1.3 → .env.example
[ ] STEP 2.1 → Database setup
[ ] STEP 2.2 → SQLAlchemy models (SEMUA)
[ ] STEP 2.3 → Alembic migration
[ ] STEP 3.1 → FastAPI main app
[ ] STEP 3.2 → Auth API
[ ] STEP 3.3 → Video API
[ ] STEP 3.4 → Clips API
[ ] STEP 4.1 → Whisper Service (CRITICAL)
[ ] STEP 4.2 → AI Brain Service (CRITICAL)
[ ] STEP 4.3 → Video Processor Service (CRITICAL)
[ ] STEP 4.4 → Copyright Check Service
[ ] STEP 4.5 → Notification Service
[ ] STEP 5   → Celery Pipeline (CRITICAL)
[ ] STEP 6.1 → Next.js setup + design system
[ ] STEP 6.2 → Layout & Navigation
[ ] STEP 6.3 → Dashboard Home
[ ] STEP 6.4 → Video Upload & Management
[ ] STEP 6.5 → Review Queue (CRITICAL UX)
[ ] STEP 6.6 → API Integration Layer
[ ] STEP 7   → YouTube Integration
[ ] STEP 8   → Requirements & Makefile
[ ] STEP 9   → README
[ ] STEP 10  → Testing
```

---

## ⚠️ CRITICAL RULES untuk Claude Sonnet

1. **Gunakan skills yang sudah diinstall** — selalu reference skill yang relevan sebelum menulis kode
2. **Jangan skip error handling** — setiap service harus punya proper exception handling
3. **Type hints wajib** — semua Python code harus fully typed, TypeScript strict mode
4. **Checkpoint system** — pipeline HARUS resumable dari titik kegagalan
5. **Async first** — semua I/O operations harus async (database, HTTP, file)
6. **Log everything** — gunakan loguru untuk structured logging di setiap stage
7. **Jangan hardcode** — semua config dari environment variables
8. **GPU-aware** — Whisper dan FFmpeg harus cek CUDA availability
9. **Production mindset** — tulis kode seolah ini akan dipakai 1000 user, bukan prototype

---

*AI Content Factory MVP — Built for local execution on Ryzen 9800X3D + RTX 4070*
*Target: 10 beta users, 100 clips processed | Timeline: 8 weeks*
