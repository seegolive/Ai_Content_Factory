#!/usr/bin/env bash
# =============================================================================
#  AI Content Factory — Setup Script (Linux / macOS / WSL2)
#  Tested: Ubuntu 24.04 + WSL2 + Docker Desktop 28.x + NVIDIA RTX 4070
#
#  Usage:
#    chmod +x setup.sh
#    ./setup.sh            # Full first-time setup
#    ./setup.sh --reset    # Wipe DB volumes and re-run migrations
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
info() { echo -e "${CYAN}[..] $*${NC}"; }
warn() { echo -e "${YELLOW}[!!] $*${NC}"; }
fail() { echo -e "${RED}[ERR]${NC} $*"; exit 1; }

RESET_DB=false
[[ "${1:-}" == "--reset" ]] && RESET_DB=true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo "   AI Content Factory — Setup"
echo "============================================================"
echo ""

# ── 1. Check Prerequisites ────────────────────────────────────────────────────
info "Checking prerequisites..."

command -v docker  >/dev/null 2>&1 || fail "Docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop"
command -v docker  >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || \
  fail "Docker Compose V2 not found. Update Docker Desktop to v4.x+"
command -v node    >/dev/null 2>&1 || warn "Node.js not found — frontend dev server won't work (optional)"
command -v npm     >/dev/null 2>&1 || warn "npm not found — frontend dev server won't work (optional)"

ok "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
ok "Docker Compose $(docker compose version --short)"

# ── 2. Create .env if missing ─────────────────────────────────────────────────
if [[ ! -f ".env" ]]; then
  info "Creating .env from template..."
  if [[ -f "backend/.env.example" ]]; then
    cp backend/.env.example .env
  else
    # Inline minimal template
    cat > .env <<'ENVEOF'
# AI Content Factory — Environment Variables
APP_ENV=development
FRONTEND_URL=http://localhost:3000

# Database
POSTGRES_PASSWORD=password
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/ai_content_factory
DATABASE_URL_SYNC=postgresql://postgres:password@postgres:5432/ai_content_factory

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Security — replace with: openssl rand -hex 32
SECRET_KEY=changeme-replace-with-openssl-rand-hex-32-output
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Google OAuth [REQUIRED] — https://console.cloud.google.com
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback

# YouTube API [REQUIRED]
YOUTUBE_API_KEY=

# Groq AI — PRIMARY free tier [REQUIRED] — https://console.groq.com/keys
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile

# OpenRouter — Fallback [REQUIRED] — https://openrouter.ai/keys
OPENROUTER_API_KEY=
OPENROUTER_MODEL=google/gemini-2.0-flash-001
OPENROUTER_FALLBACK_MODEL=openai/gpt-4o-mini

# Whisper (GPU transcription)
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

# ACRCloud — Copyright check [REQUIRED] — https://console.acrcloud.com
ACRCLOUD_HOST=
ACRCLOUD_ACCESS_KEY=
ACRCLOUD_ACCESS_SECRET=

# Telegram Bot — Notifications [REQUIRED]
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# SendGrid — Email [REQUIRED] — https://app.sendgrid.com/settings/api_keys
SENDGRID_API_KEY=
FROM_EMAIL=noreply@yourdomain.com

# Storage
STORAGE_TYPE=local
LOCAL_STORAGE_PATH=./storage
ENVEOF
  fi

  # Generate a real SECRET_KEY
  if command -v openssl >/dev/null 2>&1; then
    NEW_KEY=$(openssl rand -hex 32)
    sed -i "s|changeme-replace-with-openssl-rand-hex-32-output|${NEW_KEY}|" .env
    ok "Generated SECRET_KEY"
  fi

  ok ".env created"
  warn "Fill in required API keys in .env before running the pipeline!"
else
  ok ".env already exists — skipping"
fi

# ── 3. Create storage directories ─────────────────────────────────────────────
info "Creating storage directories..."
mkdir -p storage/{videos,clips,thumbnails,audio_samples}
ok "Storage directories ready"

# ── 4. Reset volumes if requested ────────────────────────────────────────────
if [[ "$RESET_DB" == "true" ]]; then
  warn "Resetting DB volumes (--reset flag)..."
  docker compose down -v 2>/dev/null || true
  ok "Volumes removed"
fi

# ── 5. Build Docker images ────────────────────────────────────────────────────
info "Building Docker images (this takes 5-10 min on first run — PyTorch CUDA download)..."
echo ""

# Build strategy:
#   - python:3.12-bullseye base (Debian 11 stable — no apt mirror issues)
#   - bullseye-updates repo DISABLED to avoid CDN hash mismatch (Apr 2026 issue)
#   - ffmpeg: static binary from BtbN/FFmpeg-Builds (no apt needed)
#   - psycopg2-binary: pre-compiled wheel (no gcc/libpq-dev needed)
#   - PyTorch cu124: from download.pytorch.org (fallback to CPU if GPU unavailable)

docker compose build backend celery_worker frontend
echo ""
ok "All Docker images built"

# ── 6. Start services ─────────────────────────────────────────────────────────
info "Starting all services..."
docker compose up -d
echo ""

# Wait for postgres and redis to be healthy
info "Waiting for Postgres and Redis to be ready..."
TIMEOUT=60
ELAPSED=0
until docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; do
  sleep 2; ELAPSED=$((ELAPSED+2))
  [[ $ELAPSED -ge $TIMEOUT ]] && fail "Postgres did not become healthy within ${TIMEOUT}s"
done
ok "Postgres healthy"

until docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; do
  sleep 1; ELAPSED=$((ELAPSED+1))
  [[ $ELAPSED -ge $TIMEOUT ]] && fail "Redis did not become healthy within ${TIMEOUT}s"
done
ok "Redis healthy"

# ── 7. Run database migrations ────────────────────────────────────────────────
info "Running Alembic migrations..."
docker compose exec -T backend alembic upgrade head
ok "Migrations complete (001 → 008)"

# ── 8. Install frontend dependencies (for npm run dev) ────────────────────────
if command -v npm >/dev/null 2>&1 && [[ -d "frontend" ]]; then
  if [[ ! -d "frontend/node_modules" ]]; then
    info "Installing frontend npm dependencies..."
    cd frontend && npm install --legacy-peer-deps && cd ..
    ok "Frontend dependencies installed"
  else
    ok "frontend/node_modules already exists — skipping npm install"
  fi
fi

# ── 9. Print summary ──────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo -e "   ${GREEN}Setup Complete!${NC}"
echo "============================================================"
echo ""
echo "  Services:"
docker compose ps --format "  {{.Name}}: {{.Status}}" 2>/dev/null | grep -v "^$" || docker compose ps
echo ""
echo "  Access Points:"
echo -e "    Backend API:     ${CYAN}http://localhost:8000${NC}"
echo -e "    API Docs:        ${CYAN}http://localhost:8000/docs${NC}"
echo -e "    Frontend (Docker): ${CYAN}http://localhost:3000${NC}"
echo -e "    Celery Flower:   ${CYAN}http://localhost:5555${NC}"
echo ""
echo "  To start frontend in dev mode (hot reload):"
echo -e "    ${YELLOW}cd frontend && npm run dev${NC}"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f backend       # Backend logs"
echo "    docker compose logs -f celery_worker # Worker logs"
echo "    docker compose exec backend alembic upgrade head  # Re-run migrations"
echo "    docker compose down                  # Stop all services"
echo "    ./setup.sh --reset                   # Wipe DB and restart fresh"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo "    1. Fill in API keys in .env (GROQ_API_KEY, OPENROUTER_API_KEY, etc.)"
echo "    2. Configure Google OAuth at https://console.cloud.google.com"
echo "    3. Run: make gpu-test   (verify CUDA for Whisper)"
echo "    4. Run: cd frontend && npm run dev   (start frontend dev server)"
echo ""
