# 🏭 AI CONTENT FACTORY — MVP Build Prompt v2
> Prompt ini dirancang untuk dijalankan menggunakan **Claude Sonnet** via **GitHub Copilot**
> Jalankan skills installation terlebih dahulu sebelum memulai sesi coding
> **v2 Update:** Multi-model fallback (Groq → Gemini Flash → GPT-4o-mini), gaming-specific tuning

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

Kamu adalah **Senior Fullstack Architect** yang membangun **AI Content Factory MVP** — platform produksi konten berbasis AI yang mengotomatisasi pipeline dari raw video hingga konten siap publish di YouTube.

**Use case utama (reference channel: Seego GG):**
- Content creator gaming Indonesia
- Konten: LIVE recordings 2–5 jam (Battlefield 6, Kingdom Come Deliverance II, Arc Raiders)
- Problem: tidak ada waktu untuk clip manual setelah stream
- Goal: 1 LIVE recording → 10-15 Shorts clips otomatis, siap review dalam 30 menit

**Spesifikasi hardware developer (local machine):**
- CPU: AMD Ryzen 9 9800X3D
- RAM: 32GB DDR5
- GPU: NVIDIA RTX 4070 (12GB VRAM)
- OS Target: Windows 11 / Ubuntu WSL2

**AI Model Stack (UPDATED v2):**
```
Layer 1 — Transcription (LOKAL, GPU):
└── faster-whisper large-v3 (CUDA float16, ~6GB VRAM)
    → Gratis, ~10-15x realtime, akurasi terbaik untuk Bahasa Indonesia

Layer 2 — AI Brain (CLOUD, Multi-model Fallback):
├── PRIMARY:  Groq — llama-3.3-70b-versatile (GRATIS, tercepat)
├── FALLBACK1: OpenRouter — google/gemini-2.0-flash-001 (murah, Bahasa Indonesia bagus)
└── FALLBACK2: OpenRouter — openai/gpt-4o-mini (last resort)

Layer 3 — Video Processing (LOKAL, CPU+GPU):
└── FFmpeg dengan CUDA hardware acceleration
    → Gratis, potong/resize/subtitle/QC
```

**VRAM Management (KRITIS — 12GB total):**
```
Whisper large-v3 = ~6GB → load saat stage transcription, UNLOAD setelah selesai
FFmpeg CUDA      = ~1GB → ringan, bisa overlap
SDXL (V2 nanti) = ~8GB → TIDAK di MVP, load terpisah nanti
```
Pipeline berjalan SEQUENTIAL per stage — tidak pernah 2 model besar di VRAM bersamaan.

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
│   │   │   ├── transcription.py       # Whisper local GPU
│   │   │   ├── ai_brain.py            # Multi-model fallback (Groq → Gemini → GPT-4o-mini)
│   │   │   ├── video_processor.py     # FFmpeg
│   │   │   ├── qc_service.py          # Quality Control
│   │   │   ├── copyright_check.py     # ACRCloud
│   │   │   ├── youtube_service.py     # YouTube API
│   │   │   └── notification.py        # Telegram + Email
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   └── tasks/
│   │   │       ├── __init__.py
│   │   │       ├── pipeline.py        # Main pipeline orchestrator
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
│   │   │   ├── ui/
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
   - PENTING: GPU access wajib untuk Whisper RTX 4070

5. celery_flower (monitoring)
   - image: mher/flower
   - port: 5555

6. frontend (build dari ./frontend)
   - port: 3000
   - hot reload

volumes: postgres_data, redis_data
networks: app_network (bridge)
```

---

### 1.3 Buat `.env.example`

```
Buat .env.example lengkap:

# ============================================
# DATABASE
# ============================================
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ai_content_factory
DATABASE_URL_SYNC=postgresql://postgres:password@localhost:5432/ai_content_factory

# ============================================
# REDIS & CELERY
# ============================================
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ============================================
# SECURITY
# ============================================
SECRET_KEY=your-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ============================================
# GOOGLE OAUTH & YOUTUBE
# ============================================
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback
YOUTUBE_API_KEY=

# ============================================
# AI MODELS — MULTI-MODEL FALLBACK (v2)
# ============================================

# PRIMARY: Groq (GRATIS, tercepat)
GROQ_API_KEY=
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile

# FALLBACK 1: OpenRouter — Gemini Flash
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemini-2.0-flash-001

# FALLBACK 2: OpenRouter — GPT-4o-mini (last resort)
OPENROUTER_FALLBACK_MODEL=openai/gpt-4o-mini

# ============================================
# WHISPER (LOCAL GPU)
# ============================================
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
WHISPER_CPU_FALLBACK_MODEL=medium

# ============================================
# VIDEO PROCESSING
# ============================================
FFMPEG_HWACCEL=cuda
MAX_VIDEO_SIZE_GB=10
MAX_VIDEO_DURATION_HOURS=3

# ============================================
# COPYRIGHT CHECK
# ============================================
ACRCLOUD_HOST=
ACRCLOUD_ACCESS_KEY=
ACRCLOUD_ACCESS_SECRET=

# ============================================
# NOTIFICATIONS
# ============================================
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SENDGRID_API_KEY=
FROM_EMAIL=noreply@yourdomain.com

# ============================================
# STORAGE (LOCAL untuk MVP)
# ============================================
STORAGE_TYPE=local
LOCAL_STORAGE_PATH=./storage

# Future S3/R2:
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET=
CLOUDFLARE_R2_ENDPOINT=

# ============================================
# APP CONFIG
# ============================================
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
FRONTEND_URL=http://localhost:3000
```

---

## 🗄️ STEP 2 — Database & Models

### 2.1 Setup Database dengan SQLAlchemy Async

```
Gunakan skill senior-backend.

Buat backend/app/core/database.py:
- AsyncEngine dengan asyncpg
- AsyncSessionLocal factory
- Base declarative model
- get_db dependency untuk FastAPI
- Fungsi init_db() untuk create tables

Buat backend/app/core/config.py:
- Pydantic BaseSettings
- Load dari .env file
- Validasi semua required fields
- Property computed untuk DATABASE_URL parsing
- Settings class dengan semua field dari .env.example di atas
```

### 2.2 Buat Semua SQLAlchemy Models

```
Gunakan skill senior-backend dan senior-architect.

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
  - created_at, updated_at (timezone-aware)

FILE: backend/app/models/video.py
- YoutubeAccount model:
  - id: UUID PK
  - user_id: UUID FK → users
  - channel_id: String(255) NOT NULL
  - channel_name: String(255)
  - access_token: Text (encrypted)
  - refresh_token: Text (encrypted)
  - token_expires_at: DateTime
  - content_dna: JSONB default {}
  - created_at, updated_at

- Video model:
  - id: UUID PK
  - user_id: UUID FK → users
  - youtube_account_id: UUID FK → youtube_accounts (nullable)
  - title: String(500)
  - original_url: Text
  - file_path: Text
  - file_size_mb: Float
  - duration_seconds: Float
  - status: Enum('queued','processing','review','done','error')
  - checkpoint: String(100)
  - error_message: Text
  - copyright_status: Enum('unchecked','clean','flagged')
  - transcript: Text
  - transcript_segments: JSONB
  - celery_task_id: String(255)
  - ai_provider_used: String(100)    ← BARU: track provider mana yang dipakai
  - created_at, updated_at

FILE: backend/app/models/clip.py
- Clip model:
  - id: UUID PK
  - video_id: UUID FK → videos
  - user_id: UUID FK → users
  - title: Text
  - description: Text
  - start_time: Float NOT NULL
  - end_time: Float NOT NULL
  - duration: Float
  - viral_score: Integer (0-100)
  - moment_type: String(50)          ← BARU: 'clutch','funny','achievement','rage','epic'
  - hook_text: Text
  - hashtags: JSONB
  - thumbnail_path: Text
  - clip_path_horizontal: Text       ← BARU: path per format
  - clip_path_vertical: Text         ← BARU: 9:16 untuk Shorts
  - clip_path_square: Text           ← BARU: 1:1 untuk Feed
  - format_generated: JSONB          ← BARU: {horizontal: bool, vertical: bool, square: bool}
  - qc_status: Enum('pending','passed','failed','manual_review')
  - qc_issues: JSONB
  - review_status: Enum('pending','approved','rejected')
  - reviewed_at: DateTime
  - platform_status: JSONB
  - speaker_id: String(100)
  - ai_provider_used: String(100)    ← BARU: track provider mana yang generate
  - created_at, updated_at

FILE: backend/app/models/brand_kit.py
- BrandKit model (sama seperti sebelumnya)
```

### 2.3 Alembic Migration

```
Buat initial migration: 001_initial_schema.py
Buat semua tabel dari models di atas.
Setup alembic.ini dengan DATABASE_URL dari environment.
```

---

## 🔧 STEP 3 — Backend API

### 3.1 FastAPI Main App

```
Gunakan skill senior-backend.

Buat backend/app/main.py:
- FastAPI app dengan metadata
- CORS middleware
- Exception handlers (HTTP, Validation, generic)
- Lifespan context: init DB + storage dirs
- Include semua routers prefix /api/v1
- GET /health → return status semua komponen termasuk GPU availability
- Static files untuk /storage
- Request logging middleware
```

### 3.2 Authentication API

```
Gunakan skill senior-backend.

Buat backend/app/api/routes/auth.py:
1. GET /auth/google/login → return OAuth URL
2. GET /auth/google/callback → exchange code, create/update user, return JWT
3. GET /auth/me (protected) → current user + youtube_accounts
4. POST /auth/logout → invalidate token di Redis

Buat backend/app/core/security.py:
- create_access_token, verify_token
- get_current_user dependency
- Google OAuth flow helper
```

### 3.3 Video Management API

```
Gunakan skill senior-backend.

Buat backend/app/api/routes/videos.py:
1. POST /videos/upload → multipart upload, validasi, trigger pipeline
2. POST /videos/from-url → YouTube URL input, trigger pipeline
3. GET /videos → list dengan pagination + status filter
4. GET /videos/{id} → detail + clips
5. DELETE /videos/{id} → soft delete + cancel task
6. GET /videos/{id}/status → lightweight polling endpoint
```

### 3.4 Clips & Review API

```
Gunakan skill senior-backend.

Buat backend/app/api/routes/clips.py:
1. GET /videos/{id}/clips → list dengan filter viral_score, qc_status
2. PATCH /clips/{id}/review → approve/reject
3. POST /clips/bulk-review → bulk action
4. PATCH /clips/{id} → edit title, description, hashtags
5. POST /clips/{id}/publish → trigger distribute task
6. GET /clips/{id}/stream → streaming untuk preview player
```

---

## ⚙️ STEP 4 — Core Services

### 4.1 Transcription Service (Whisper Local GPU)

```
Gunakan skill senior-backend.

Buat backend/app/services/transcription.py:

Class WhisperTranscriptionService:

- __init__:
  - Load faster-whisper model: large-v3
  - Device: cuda, compute_type: float16
  - Cek CUDA availability, fallback ke CPU + model medium jika tidak ada GPU
  - Singleton pattern: load sekali, reuse

- async transcribe(video_path: str) → TranscriptResult:
  - Run dalam asyncio thread pool executor (non-blocking)
  - Output: full_text, segments [{id, start, end, text, confidence}]
  - Language detection otomatis
  - Log GPU memory usage sebelum dan sesudah

- async unload_model():
  - KRITIS: unload model dari VRAM setelah transcription selesai
  - Panggil torch.cuda.empty_cache()
  - Ini membebaskan ~6GB VRAM untuk proses berikutnya

- handle_errors:
  - CUDA OOM → unload, fallback CPU + model medium, retry
  - File not found → VideoNotFoundError
  - Corrupt audio → TranscriptionError

TranscriptResult dataclass:
- full_text: str
- segments: List[TranscriptSegment]
- language: str
- duration: float
- word_count: int
- confidence_avg: float
```

### 4.2 AI Brain Service — Multi-Model Fallback (UPDATED v2)

```
Gunakan skill senior-backend dan senior-prompt-engineer.

Buat backend/app/services/ai_brain.py:

PROVIDER_CHAIN = [
  {
    "name": "Groq",
    "base_url": settings.GROQ_BASE_URL,       # https://api.groq.com/openai/v1
    "api_key": settings.GROQ_API_KEY,
    "model": settings.GROQ_MODEL,             # llama-3.3-70b-versatile
  },
  {
    "name": "OpenRouter Gemini Flash",
    "base_url": settings.OPENROUTER_BASE_URL,
    "api_key": settings.OPENROUTER_API_KEY,
    "model": settings.OPENROUTER_MODEL,       # google/gemini-2.0-flash-001
  },
  {
    "name": "OpenRouter GPT-4o-mini",
    "base_url": settings.OPENROUTER_BASE_URL,
    "api_key": settings.OPENROUTER_API_KEY,
    "model": settings.OPENROUTER_FALLBACK_MODEL,  # openai/gpt-4o-mini
  },
]

Class AIBrainService:

- async _call_with_fallback(messages, max_tokens=4000) → tuple[str, str]:
  """
  Coba provider satu per satu secara berurutan.
  Return: (response_text, provider_name_yang_berhasil)
  
  Skip ke provider berikutnya jika:
  - HTTP 429 (rate limit)
  - HTTP 500/503 (server error)
  - Timeout > 60 detik
  - Connection error
  
  Raise Exception hanya jika SEMUA provider gagal.
  """
  Implementasi:
  - Loop PROVIDER_CHAIN
  - httpx.AsyncClient per provider
  - Log provider yang dicoba dan hasilnya
  - Simpan provider_name yang berhasil untuk disimpan ke DB

- async analyze_transcript(transcript: TranscriptResult, game_title: str, channel_name: str) → AIAnalysisResult:
  """
  PROMPT GAMING-SPECIFIC (gunakan skill senior-prompt-engineer):
  
  System prompt:
  Kamu adalah analis konten gaming Indonesia yang ahli mendeteksi momen viral
  dari transcript stream. Kamu memahami konteks gaming Indonesia:
  - Kata-kata exclamation gamer: "wah gila", "aduh", "yes!", "dari mana tuh", "ez", "gg"
  - Tipe momen: clutch, rage, funny, achievement, fail, epic comeback
  - Preferensi audiens gaming Indonesia: reaksi ekspresif, momen tidak terduga
  
  Output HANYA JSON valid. Tidak ada teks di luar JSON.
  
  JSON Schema:
  {
    "clips": [
      {
        "start_time": float,
        "end_time": float,
        "viral_score": int (0-100),
        "moment_type": "clutch|funny|achievement|rage|epic|fail",
        "titles": ["judul 1", "judul 2", "judul 3"],
        "hook_text": "teks 5 detik pertama yang menarik",
        "description": "deskripsi SEO YouTube Bahasa Indonesia",
        "hashtags": ["tag1", "tag2", ...],
        "reason": "kenapa momen ini viral"
      }
    ],
    "summary": "ringkasan singkat video ini"
  }
  
  Viral scoring untuk gaming content (0-100):
  - Reaksi ekspresif streamer (0-30): teriak, exclamation, shock
  - Kelangkaan momen (0-25): clutch 1v4, never-seen-before, achievement
  - Hook strength 5 detik pertama (0-25): langsung action atau tension
  - Relatability & shareable (0-20): "ini gue banget", "tag temen lo"
  """
  
  Setelah dapat response:
  - Parse JSON dengan error handling
  - Jika JSON invalid: retry dengan instruksi "output HANYA JSON valid"
  - Max retry JSON parsing: 2x
  - Return AIAnalysisResult dengan provider_used

- async generate_titles(clip_info: dict, game_title: str) → List[str]:
  """
  Generate 3 title variant gaming Indonesia.
  Style options: emotional, curiosity gap, achievement, funny
  Contoh output:
  - "Gak Nyangka Bisa Solo Squad di Battlefield 6 😱"
  - "Momen Paling Gila Gue di Battlefield 6 Indonesia"  
  - "Ini Yang Terjadi Waktu Gue All-In di Detik Terakhir..."
  """

AIAnalysisResult dataclass:
- clips: List[ClipSuggestion]
- summary: str
- processing_time: float
- provider_used: str      ← track provider mana yang berhasil
- tokens_used: int
- model_used: str

PENTING:
- Semua provider compatible dengan OpenAI API format → tidak perlu kode berbeda per provider
- Log setiap provider attempt untuk debugging
- Simpan provider_used ke DB (field ai_provider_used di Video dan Clip model)
```

### 4.3 Video Processor Service (FFmpeg)

```
Gunakan skill senior-backend.

Buat backend/app/services/video_processor.py:

Class VideoProcessorService:

- async cut_clip(input_path, output_path, start_time, end_time) → str:
  - FFmpeg: -ss {start} -to {end} -c:v libx264 -c:a aac
  - Hardware accel: -hwaccel cuda -hwaccel_output_format cuda
  - Quality: -crf 23 -preset fast
  - Fallback ke CPU jika CUDA tidak available

- async resize_for_platform(input_path, clip_id) → Dict[str, str]:
  Generate 3 format sekaligus:
  - 'horizontal': 1920x1080 (16:9) → clips/{clip_id}_horizontal.mp4
  - 'vertical':   1080x1920 (9:16) → clips/{clip_id}_vertical.mp4  ← SHORTS
  - 'square':     1080x1080 (1:1)  → clips/{clip_id}_square.mp4
  
  Smart cropping strategy:
  - Deteksi area aksi (tengah frame untuk gaming = area paling aktif)
  - Padding dengan blur background jika letterbox
  - Jangan stretch atau distort

- async burn_subtitles(input_path, segments, output_path) → str:
  - Convert segments ke .srt
  - Burn dengan ffmpeg -vf subtitles
  - Style: FontSize=52, Bold=1, PrimaryColour=&HFFFFFF, OutlineColour=&H000000, Outline=2
  - Posisi: bawah tengah dengan margin 60px

- async run_qc_check(clip_path) → QCResult:
  - Silence: silencedetect -45dB > 3 detik → flag
  - Audio clip: loudnorm peak > -1dB → flag
  - Blur: laplacian variance sampling per 2 detik → flag jika < threshold
  - Black frame: blackdetect → flag jika > 2 detik
  - Durasi: flag jika < 15 detik atau > 10 menit

- _run_ffmpeg(cmd) → result:
  - asyncio.create_subprocess_exec
  - Timeout: 30 menit
  - Capture stderr untuk error parsing
  - Raise VideoProcessingError jika returncode != 0
```

### 4.4 Copyright Check Service

```
Buat backend/app/services/copyright_check.py:

Class CopyrightCheckService:

- async check_audio(video_path: str) → CopyrightResult:
  - Extract 30 detik audio dari tengah video via FFmpeg
  - Send ke ACRCloud API
  - Parse: music name, artist, label, confidence
  - Return CopyrightResult

CopyrightResult: is_flagged, matched_music, artist, confidence, status
```

### 4.5 Notification Service

```
Buat backend/app/services/notification.py:

Class NotificationService:

- async send_telegram(message: str) → bool:
  - Retry 3x
  - HTML parse mode dengan emoji

- async notify_job_complete(video, clips_count, user, provider_used):
  Format:
  "✅ <b>{video.title}</b>
  
  📊 {clips_count} clips siap direview
  🤖 AI: {provider_used}
  ⏱️ Selesai dalam {duration}
  
  👉 Buka dashboard untuk review"

- async notify_job_error(video, error, stage, user):
  Format:
  "❌ Error di stage <b>{stage}</b>
  Video: {video.title}
  Error: {error}
  
  Pipeline akan resume dari checkpoint ini."

- async notify_provider_fallback(from_provider, to_provider, reason):
  Format:
  "⚠️ AI fallback: {from_provider} → {to_provider}
  Alasan: {reason}"
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

Buat backend/app/workers/tasks/pipeline.py:

@celery_app.task(bind=True, max_retries=3)
def process_video_pipeline(self, video_id: str):
  """
  Main pipeline dengan checkpoint system + VRAM management.
  
  STAGES & CHECKPOINTS:
  1. input_validated  → validasi file + copyright pre-check
  2. transcript_done  → Whisper GPU → UNLOAD VRAM setelah selesai
  3. ai_done          → Multi-model fallback analysis (Groq → Gemini → GPT-4o-mini)
  4. qc_done          → Auto QC per clip suggestion
  5. clips_done       → FFmpeg: cut + resize 3 format + burn subtitle
  6. review_ready     → Notify user via Telegram
  
  VRAM Flow:
  Stage 2: torch.cuda.empty_cache() sebelum load Whisper
           Whisper.transcribe() → ~6GB VRAM
           Whisper.unload() + torch.cuda.empty_cache() → VRAM bebas
  Stage 5: FFmpeg CUDA accel → ~1GB VRAM (ringan)
  
  Checkpoint resume:
  - Load video dari DB
  - Cek checkpoint field
  - Skip semua stage sebelum checkpoint
  - Lanjut dari stage berikutnya
  
  Error handling:
  - Update video.status = 'error'
  - Simpan error_message + stage yang gagal
  - Notify user
  - Celery retry dengan exponential backoff
  
  Idempotency:
  - Cek existing clips sebelum create baru
  - Cek existing files sebelum FFmpeg run
  - Upsert, bukan insert
  """
  
  CHECKPOINT_ORDER = [
    'input_validated',
    'transcript_done',
    'ai_done',
    'qc_done',
    'clips_done',
    'review_ready'
  ]
```

---

## 🎨 STEP 6 — Frontend Dashboard

### 6.1 Setup Next.js Project

```
Gunakan skill senior-frontend, ui-ux-pro-max, ui-design-system.

Setup Next.js 15:
- TypeScript strict mode
- TailwindCSS v4
- shadcn/ui (full install)
- Zustand state management
- TanStack Query untuk server state
- Axios HTTP client

Design System:
- Color Palette (dark theme):
  - Background: #0A0A0F
  - Surface: #13131A
  - Border: #1E1E2E
  - Primary: #6C63FF (electric violet)
  - Secondary: #00D4AA (cyber teal)
  - Accent: #FF6B6B (coral)
  - Text Primary: #E8E8F0
  - Text Muted: #6B6B8A

- Typography:
  - Display: 'Space Grotesk'
  - Body: 'Inter'
  - Mono: 'JetBrains Mono' (metrics, numbers)

- Style: glassmorphism, subtle borders, 200ms transitions
```

### 6.2 Layout & Navigation

```
Buat Sidebar.tsx:
- Fixed 240px, collapsible ke 64px
- Nav: Dashboard, Videos, Review Queue, Analytics (disabled), Settings
- Bottom: user avatar + plan badge + logout

Buat Header.tsx:
- Breadcrumb, notification bell, user menu
- Status bar: active jobs + AI provider yang sedang dipakai

Buat dashboard/layout.tsx:
- Sidebar + main, responsive
```

### 6.3 Dashboard Home Page

```
Buat dashboard/page.tsx:

1. Stats Overview:
   - Total Videos, Clips Generated, Pending Review, Published
   - Trend indicator
   - Tambahkan: "AI Provider Today" badge (menampilkan provider yang paling sering dipakai)

2. Active Processing Jobs:
   - Progress bar per stage
   - Stage labels: Validated → Transcribing (GPU) → Analyzing (AI) → QC → Processing → Ready
   - Tampilkan provider AI yang sedang dipakai: "🤖 Groq · llama-3.3-70b"
   - Cancel button
   - Auto-refresh 3 detik

3. Review Queue Quick Access:
   - 5 clips viral score tertinggi
   - Thumbnail, title, score badge, approve/reject

4. Recent Videos list
```

### 6.4 Video Upload & Management Page

```
Buat videos/page.tsx:
- Drag & drop upload zone
- YouTube URL input
- Video library grid dengan status badge
- Filter: All, Processing, Review, Done, Error

Buat VideoUploader.tsx:
- File validation (format, size)
- Progress bar dengan speed indicator
- Error state dengan retry
```

### 6.5 Review Queue Page (PRIORITAS TINGGI)

```
Gunakan skill ui-ux-pro-max.

Buat review/page.tsx — halaman yang paling sering dipakai:

Layout split view:
- Left 380px: clip list sorted by viral_score DESC
  - Badge moment_type: 🎯 Clutch, 😂 Funny, 🏆 Achievement, 😤 Rage, ⚡ Epic
  - Multi-select untuk bulk action

- Right main panel:
  1. Video preview player (HTML5)
     - Custom controls
     - Loop clip button
     - Format toggle: Horizontal / Vertical / Square
     
  2. Clip info (editable inline):
     - Title (click to edit)
     - Viral score + moment_type badge
     - Hook text
     - Hashtags (chips, editable)
     - Description
     - "Generated by: Groq · llama-3.3-70b" label kecil di bawah
     
  3. Action bar (sticky bottom):
     - Reject (merah) | Approve (hijau, prominent)
     - Keyboard shortcuts: A=Approve, R=Reject, J/K=navigate, Space=play

Keyboard shortcuts wajib ada — ini fitur utama untuk efisiensi review.
```

### 6.6 API Integration Layer

```
Gunakan skill senior-frontend.

Buat lib/api.ts:
- Axios instance dengan JWT interceptor
- 401 → redirect login
- 429 → rate limit toast

Buat hooks TanStack Query:
- useVideos(), useVideo(id), useVideoStatus(id) polling 3 detik
- useClips(videoId), useMutations

Buat stores Zustand:
- videoStore: videos, activeVideoId, processingJobs
- uiStore: sidebarCollapsed, selectedClips, reviewActiveClipId
```

---

## 🔑 STEP 7 — YouTube Integration

```
Buat backend/app/services/youtube_service.py:

Class YouTubeService:
- async upload_video(clip_path, title, description, tags, privacy='unlisted')
  CATATAN: Gunakan 'unlisted' untuk beta testing — hemat quota
- async get_channel_info(access_token) → ChannelInfo
- async refresh_access_token(refresh_token) → str
- async check_upload_quota() → QuotaStatus
  YouTube quota: 10.000 units/day, 1 upload = 1600 units
  Track di Redis: f"yt_quota:{channel_id}:{date}"
  Warn jika > 7.000 units
```

---

## ✅ STEP 8 — Requirements & Makefile

### 8.1 Backend Requirements

```
Buat backend/requirements.txt:

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

# AI/ML — Whisper Local
faster-whisper==1.1.0
# torch install terpisah (lihat catatan)

# HTTP Client (untuk semua AI provider)
httpx==0.28.0
aiohttp==3.11.0
tenacity==9.0.0   ← retry logic untuk semua provider

# Auth
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
google-auth==2.37.0
google-auth-oauthlib==1.2.1
google-api-python-client==2.154.0

# Video Processing
ffmpeg-python==0.2.0

# Notification
python-telegram-bot==21.9
sendgrid==6.11.0

# Config
pydantic-settings==2.7.0
python-dotenv==1.0.1
loguru==0.7.3

# Storage
boto3==1.35.0

# Testing
pytest==8.3.0
pytest-asyncio==0.24.0

---
INSTALL TORCH DENGAN CUDA (jalankan manual, bukan via requirements.txt):
pip install torch==2.5.1+cu124 torchaudio==2.5.1+cu124 --index-url https://download.pytorch.org/whl/cu124
```

### 8.2 Makefile

```
Buat Makefile dengan commands:

make setup           → Install deps, copy .env.example → .env
make dev             → Start docker-compose
make down            → Stop semua containers
make logs            → Tail semua logs
make logs-worker     → Tail celery worker logs
make migrate         → Alembic upgrade head
make makemigrations  → Buat migration baru (prompt nama)
make shell-backend   → Bash ke backend container
make shell-db        → Psql ke database
make test            → Run pytest
make lint            → Ruff + mypy
make format          → Black + isort
make redis-cli       → Redis CLI
make flower          → Buka Flower di browser
make install-whisper → Download faster-whisper large-v3
make install-torch   → Install torch CUDA 12.4 untuk RTX 4070
make gpu-test        → Test CUDA + Whisper availability
make ai-test         → Test semua 3 AI providers (Groq, Gemini, GPT-4o-mini)
make clean           → Cleanup pycache

Tambahkan command make ai-test yang:
1. Test Groq dengan prompt sederhana → print response + latency
2. Test OpenRouter Gemini Flash → print response + latency
3. Test OpenRouter GPT-4o-mini → print response + latency
4. Print tabel hasil: Provider | Status | Latency | Model

ASCII art header di semua output:
  ╔═══════════════════════════════╗
  ║   AI CONTENT FACTORY v2       ║
  ║   Local Setup · RTX 4070      ║
  ╚═══════════════════════════════╝
```

---

## 📝 STEP 9 — README

```
Buat README.md:

1. Project Overview + badges (Python, FastAPI, Next.js, Groq, status: MVP)
2. Architecture Diagram (ASCII):

   LIVE Recording (2-5 jam)
          ↓
   [Whisper large-v3] ← RTX 4070 GPU (lokal, gratis)
          ↓ transcript + timestamps
   [Groq llama-3.3-70b] ← Primary AI (cloud, gratis)
      ↓ fallback        ↓ viral clips + titles
   [Gemini Flash]    [FFmpeg CUDA] ← RTX 4070 (lokal)
      ↓ fallback        ↓ cut + resize + subtitle
   [GPT-4o-mini]    [Review Dashboard]
                         ↓ approve
                    [YouTube Shorts] ✅

3. Prerequisites: Node 20+, Python 3.12+, Docker, NVIDIA GPU, CUDA 12.4
4. Quick Start (7 langkah termasuk torch CUDA install)
5. AI Provider Setup: cara dapat API key Groq (gratis) + OpenRouter
6. Environment Variables reference
7. GPU Setup: WSL2 CUDA guide untuk Windows 11
8. make ai-test untuk verify semua provider
9. Troubleshooting: CUDA OOM, rate limit, provider fallback
10. Pipeline stages explanation
11. Roadmap V1 → V4
```

---

## 🧪 STEP 10 — Testing & Validation

```
Gunakan skill code-reviewer.

tests/test_services/test_ai_brain.py:
- Test _call_with_fallback dengan mock semua 3 provider
- Test: Groq berhasil → tidak coba provider lain
- Test: Groq gagal (429) → otomatis coba Gemini
- Test: Groq + Gemini gagal → coba GPT-4o-mini
- Test: Semua gagal → raise Exception
- Test JSON parsing robustness (malformed → retry)
- Test gaming-specific prompt output (ada moment_type field)

tests/test_services/test_transcription.py:
- Test CUDA detection
- Test model unload setelah transcription (VRAM freed)
- Test CPU fallback

tests/test_services/test_video_processor.py:
- Test 3 format output (horizontal, vertical, square)
- Test QC check detection

tests/test_api/test_videos.py:
- Test upload endpoint
- Test status polling
- Test auth protection

tests/conftest.py:
- Async DB setup
- Mock semua 3 AI providers
- Mock Whisper (skip actual GPU dalam CI)
```

---

## 🎯 EXECUTION ORDER

```
[ ] STEP 1.1  → Project structure
[ ] STEP 1.2  → docker-compose.yml (dengan GPU support)
[ ] STEP 1.3  → .env.example (dengan 3 AI provider config)
[ ] STEP 2.1  → Database setup
[ ] STEP 2.2  → SQLAlchemy models (dengan field ai_provider_used)
[ ] STEP 2.3  → Alembic migration
[ ] STEP 3.1  → FastAPI main app
[ ] STEP 3.2  → Auth API
[ ] STEP 3.3  → Video API
[ ] STEP 3.4  → Clips API
[ ] STEP 4.1  → Whisper Service + VRAM management (CRITICAL)
[ ] STEP 4.2  → AI Brain Service + multi-model fallback (CRITICAL)
[ ] STEP 4.3  → Video Processor + 3 format output (CRITICAL)
[ ] STEP 4.4  → Copyright Check Service
[ ] STEP 4.5  → Notification Service
[ ] STEP 5    → Celery Pipeline + VRAM flow (CRITICAL)
[ ] STEP 6.1  → Next.js setup + design system
[ ] STEP 6.2  → Layout & Navigation
[ ] STEP 6.3  → Dashboard Home (dengan AI provider indicator)
[ ] STEP 6.4  → Video Upload & Management
[ ] STEP 6.5  → Review Queue + keyboard shortcuts (CRITICAL UX)
[ ] STEP 6.6  → API Integration Layer
[ ] STEP 7    → YouTube Integration
[ ] STEP 8.1  → Requirements (semua 3 provider via httpx)
[ ] STEP 8.2  → Makefile (dengan make ai-test)
[ ] STEP 9    → README
[ ] STEP 10   → Tests (cover semua 3 provider fallback)
```

---

## ⚠️ CRITICAL RULES

1. **Multi-model fallback wajib** — tidak boleh hardcode satu provider, selalu gunakan PROVIDER_CHAIN
2. **VRAM management ketat** — Whisper HARUS unload setelah selesai, panggil torch.cuda.empty_cache()
3. **Checkpoint system** — pipeline HARUS resumable, tidak boleh ulang dari awal
4. **Track provider_used** — simpan ke DB dan tampilkan di UI, berguna untuk debugging dan optimasi
5. **Gaming-specific prompts** — semua AI prompt harus aware konteks gaming Indonesia
6. **Bahasa Indonesia di output AI** — titles, descriptions, hashtags, notifications semua Indonesia
7. **Async first** — semua I/O harus async
8. **Log everything** — gunakan loguru, log setiap provider attempt
9. **Type hints wajib** — Python fully typed, TypeScript strict mode
10. **make ai-test harus hijau** — semua 3 provider harus verify sebelum mulai development

---

## 📊 AI Provider Quick Reference

```
Provider          Model                      Biaya      Speed    ID Quality
─────────────────────────────────────────────────────────────────────────
Groq (PRIMARY)    llama-3.3-70b-versatile   GRATIS     ⚡⚡⚡    ⭐⭐⭐⭐
Gemini Flash      google/gemini-2.0-flash-001  ~$0.07/1M  ⚡⚡     ⭐⭐⭐⭐⭐
GPT-4o-mini       openai/gpt-4o-mini         ~$0.15/1M  ⚡⚡     ⭐⭐⭐⭐

Estimasi cost MVP (100 video/bulan, ~8K token per video):
- Groq saja (normal):     $0/bulan
- Jika semua ke Gemini:   ~$0.06/bulan
- Jika semua ke GPT-mini: ~$0.12/bulan
```

---

*AI Content Factory MVP v2 — Built for local execution*
*Hardware: Ryzen 9800X3D + RTX 4070 12GB + 32GB DDR5*
*AI Stack: Whisper (lokal) + Groq/Gemini/GPT-4o-mini (cloud fallback)*
*Use case: Seego GG — Gaming Indonesia LIVE recordings → Shorts otomatis*
*Target: 10 beta users, 100 clips/bulan | Timeline: 8 minggu*
