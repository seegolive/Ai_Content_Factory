# 🏭 AI Content Factory

![Python](https://img.shields.io/badge/Python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![Next.js](https://img.shields.io/badge/Next.js-15-black) ![AI](https://img.shields.io/badge/AI-Claude%20Sonnet%20%7C%20Groq%20%7C%20Gemini-purple) ![GPU](https://img.shields.io/badge/GPU-RTX%204070%20av1__nvenc-76b900) ![Status](https://img.shields.io/badge/Status-MVP-orange)

> Platform otomasi produksi konten gaming: upload LIVE recording → AI transkripsi → deteksi momen viral → potong clip → QC → review → publish ke YouTube Shorts.
>
> **Use case:** Seego GG — gaming Indonesia (Battlefield 6, KCD2, Arc Raiders)

---

## Architecture

```
LIVE Recording (2–5 jam)
       ↓
[Whisper large-v3] ← RTX 4070 GPU (lokal, gratis, ~6GB VRAM)
       ↓ transcript + timestamps
[Claude Sonnet 4.5] ← PRIMARY AI (OpenRouter, terbaik)
   ↓ 429/fail         ↓ viral clips + titles (Bahasa Indonesia)
[Groq llama-3.3-70b]  [FFmpeg av1_nvenc] ← RTX 4070 AV1 HW encoder
   ↓ fail              ↓ cut + resize 3 format + burn subtitle
[Gemini Flash]       [Review Dashboard]
                          ↓ approve (A/R/J/K keyboard shortcuts)
                     [Publish Page] → YouTube Shorts ✅
```

### VRAM Management (RTX 4070 12GB)
```
Stage 2 Transcription : Whisper large-v3 = ~6GB → load → UNLOAD setelah selesai
Stage 5 Video Process : FFmpeg av1_nvenc  = ~1GB → GPU AV1 HW encoder (RTX 40xx)
SDXL (V2 nanti)       : ~8GB → NOT in MVP, load terpisah
```
Pipeline berjalan SEQUENTIAL — tidak pernah 2 model besar di VRAM bersamaan.

---

## Prerequisites

- **Node.js** 20+
- **Python** 3.12+
- **Docker** + Docker Compose
- **NVIDIA GPU** (RTX 4070 12GB recommended) + drivers
- **CUDA** 12.4

---

## Quick Start (7 langkah)

```bash
# 1. Clone dan masuk ke folder
cd ai-content-factory

# 2. Copy env dan konfigurasi
cp .env.example .env
# Edit .env — isi GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GROQ_API_KEY, OPENROUTER_API_KEY

# 3. Install PyTorch dengan CUDA (jalankan SEKALI — tidak via requirements.txt)
make install-torch

# 4. Start semua services
make dev

# 5. Run database migrations
make migrate

# 6. Verify semua AI provider aktif
make ai-test

# 7. Buka browser
open http://localhost:3000
```

---

## AI Provider Setup

### Claude Sonnet (PRIMARY — via OpenRouter)
1. Daftar di [openrouter.ai](https://openrouter.ai)
2. Buat API key
3. Set `OPENROUTER_API_KEY=sk-or-...` di `.env`
4. Model: `anthropic/claude-sonnet-4-5` (default)

### Groq (Fallback 1 — GRATIS)
1. Daftar di [console.groq.com](https://console.groq.com)
2. Buat API key
3. Set `GROQ_API_KEY=gsk_...` di `.env`

### Gemini Flash (Fallback 2)
Sudah via OpenRouter — tidak perlu konfigurasi tambahan.

### Verify semua provider:
```bash
make ai-test
# Output:
#   Provider                     Model                               Status       Latency
#   ──────────────────────────────────────────────────────────────────────────────────────
#   Claude Sonnet                anthropic/claude-sonnet-4-5         ✅ OK        450ms
#   Groq                         llama-3.3-70b-versatile             ✅ OK        320ms
#   OpenRouter Gemini            google/gemini-2.0-flash-001         ✅ OK        890ms
```

---

## Environment Variables

Key variables (lihat `.env.example` untuk list lengkap):

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key (primary AI + fallback) |
| `GROQ_API_KEY` | Groq API key (fallback 1, gratis) |
| `OPENROUTER_MODEL` | `anthropic/claude-sonnet-4-5` (default primary) |
| `OPENROUTER_FALLBACK_MODEL` | `google/gemini-2.0-flash-001` (fallback 2) |
| `GOOGLE_CLIENT_ID` | Google OAuth App client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth App client secret |
| `WHISPER_MODEL` | `large-v3` (default, terbaik) |
| `WHISPER_DEVICE` | `cuda` for GPU, `cpu` fallback |
| `ACRCLOUD_*` | ACRCloud credentials untuk copyright check |
| `TELEGRAM_BOT_TOKEN` | Telegram bot untuk notifikasi |

---

## AI Provider Cost Estimate

| Provider | Model | Biaya | Speed | ID Quality |
|---|---|---|---|---|
| **Claude Sonnet (PRIMARY)** | anthropic/claude-sonnet-4-5 | ~$3/1M token | ⚡⚡ | ⭐⭐⭐⭐⭐ |
| **Groq (Fallback 1)** | llama-3.3-70b-versatile | **GRATIS** | ⚡⚡⚡ | ⭐⭐⭐⭐ |
| Gemini Flash (Fallback 2) | google/gemini-2.0-flash-001 | ~$0.07/1M token | ⚡⚡ | ⭐⭐⭐⭐⭐ |

**Estimasi MVP (100 video/bulan, ~8K token/video):**
- Normal (Claude semua): **~$2.40/bulan**
- Jika fallback ke Groq: **$0/bulan**
- Jika fallback ke Gemini: **~$0.06/bulan**

---

## Development

```bash
make dev           # Start semua Docker containers
make logs          # Tail semua logs
make logs-worker   # Tail Celery worker only
make flower        # Celery monitor at :5555
make redis-cli     # Redis CLI

make migrate       # Apply migrations
make makemigrations  # Create migration baru
make shell-backend # Bash ke backend container
make shell-db      # psql ke database

make test          # Run pytest
make lint          # Ruff + mypy
make format        # Black + isort

make ai-test       # Test semua 3 AI provider + print latency tabel
make gpu-test      # Cek CUDA + VRAM availability
make install-torch # Install PyTorch CUDA 12.4
make install-whisper  # Download Whisper large-v3 model
```

### Pipeline test manual:
```bash
# 1. Login di http://localhost:3000
# 2. Buka halaman Videos → upload MP4 atau paste YouTube URL
# 3. Watch progress di Dashboard (stage: Validated → Transcribing → Analyzing → QC → Processing → Ready)
# 4. Review clips di Review Queue
#    Keyboard shortcuts: A=approve, R=reject, J/K=navigate, Space=play
```

---

## Pipeline Stages

| Stage | Checkpoint | Description |
|---|---|---|
| 1 | `input_validated` | File check + ACRCloud copyright pre-scan |
| 2 | `transcript_done` | Whisper large-v3 transkripsi (GPU) → UNLOAD VRAM |
| 3 | `ai_done` | Multi-model AI (Groq→Gemini→GPT-4o-mini) viral scoring |
| 4 | `qc_done` | Quality control gate (silence, blur, black frame) |
| 5 | `clips_done` | FFmpeg: cut + resize 3 format + burn subtitle |
| 6 | `review_ready` | Notif Telegram, clips siap direview |

Pipeline **checkpoint-resumable** — jika stage gagal, retry lanjut dari checkpoint terakhir.

### Clip Moment Types
Review Queue menampilkan badge per momen:

| Badge | Type | Deskripsi |
|---|---|---|
| 🎯 Clutch | `clutch` | 1vX, menang tipis, comeback dramatis |
| 😂 Funny | `funny` | Momen lucu, fail, humor |
| 🏆 Achievement | `achievement` | First kill, milestone, unlock |
| 😤 Rage | `rage` | Frustasi, emosi, rage quit |
| ⚡ Epic | `epic` | Momen luar biasa, highlight |
| 💀 Fail | `fail` | Kesalahan lucu, unexpected death |

---

## GPU Setup (Windows WSL2 + CUDA)

```bash
# 1. Install NVIDIA drivers untuk Windows (bukan WSL)
# 2. Install CUDA toolkit di WSL2:
sudo apt-get install -y nvidia-cuda-toolkit

# 3. Verify GPU accessible:
nvidia-smi

# 4. Docker GPU access sudah dikonfigurasi di docker-compose.yml
#    (celery_worker service punya nvidia device reservation +
#     /usr/lib/wsl/lib mounted untuk libnvidia-encode)

# 5. Test dari dalam container:
make gpu-test
# Output: CUDA available: True | GPU: NVIDIA GeForce RTX 4070 | VRAM: 12.0 GB
# FFmpeg encoder: av1_nvenc (RTX 40xx AV1 hardware encoder)
```

---

## Troubleshooting

**Claude Sonnet rate limit / error**: Akan otomatis fallback ke Groq, lalu Gemini Flash. Log tersimpan di `make logs-worker`.

**Whisper fallback ke CPU**: CUDA tidak tersedia di container. Cek `nvidia-smi` di dalam container:
```bash
docker compose exec celery_worker nvidia-smi
```

**FFmpeg NVENC tidak bekerja (WSL2)**: `libnvidia-encode.so.1` harus di-mount dari host WSL2. Sudah dikonfigurasi di `docker-compose.yml` via `volumes: - /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro`. Jika masih gagal, cek:
```bash
docker exec ai-content-factory-celery_worker-1 bash -c "ls /usr/lib/wsl/lib/libnvidia-encode*"
```

**Database connection refused**: Tunggu postgres healthcheck pass, atau jalankan `make dev` lagi.

**AI semua provider gagal**: Cek API key di `.env`, lalu jalankan `make ai-test` untuk diagnosa.

**YouTube upload gagal**: Pastikan OAuth scope include `youtube.upload`. Re-auth via `/auth/google/login`.

---

## Roadmap

| Version | Features |
|---|---|
| **V1 (MVP) ✅** | Upload, transcribe, AI clip detection, review queue, publish page, YouTube publish |
| **V1.1 ✅** | Analytics dashboard, crop config, facecam/game detector, channel config |
| **V2** | SDXL thumbnail generation, multi-channel support, brand kits |
| **V3** | TikTok/Instagram/Reels distribution, advanced analytics |
| **V4** | SaaS multi-tenant, billing, team collaboration |

---

*Built for local execution — Ryzen 9800X3D + RTX 4070 12GB + 32GB DDR5*
*AI Stack: Whisper (lokal GPU) + Claude Sonnet (primary) + Groq/Gemini (fallback)*
*GPU Encoder: FFmpeg av1_nvenc (RTX 40xx AV1 hardware) → libx264 fallback*
*Use case: Seego GG — Gaming Indonesia LIVE recordings → Shorts otomatis*
*Target: 10 beta users, 100 clips/bulan*

