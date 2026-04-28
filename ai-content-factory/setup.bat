@echo off
setlocal EnableDelayedExpansion
:: =============================================================================
::  AI Content Factory — Setup Script (Windows)
::  Requires: Docker Desktop + WSL2 + Node.js (optional, for frontend dev)
::
::  Usage:
::    Double-click setup.bat       (Full first-time setup)
::    setup.bat --reset            (Wipe DB volumes and re-run)
::
::  Run as Administrator for best results.
:: =============================================================================

title AI Content Factory — Setup

set "RESET_DB=false"
if "%~1"=="--reset" set "RESET_DB=true"

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

echo.
echo ============================================================
echo    AI Content Factory -- Setup (Windows)
echo ============================================================
echo.

:: ── 1. Check Prerequisites ──────────────────────────────────────────────────
echo [..] Checking prerequisites...

where docker >nul 2>&1
if errorlevel 1 (
  echo [ERR] Docker not found.
  echo       Install Docker Desktop: https://www.docker.com/products/docker-desktop
  echo       Make sure WSL2 backend is enabled in Docker Desktop settings.
  pause & exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
  echo [ERR] Docker Compose V2 not found. Update Docker Desktop to v4.x+
  pause & exit /b 1
)

for /f "tokens=3 delims= " %%v in ('docker --version') do echo [OK]  Docker %%v
docker compose version --short > nul 2>&1 && echo [OK]  Docker Compose V2 found

where node >nul 2>&1
if errorlevel 1 (
  echo [!!] Node.js not found -- frontend dev server won't work (optional)
  echo      Download: https://nodejs.org/
) else (
  for /f "delims=" %%v in ('node --version') do echo [OK]  Node.js %%v
)

:: ── 2. Create .env if missing ────────────────────────────────────────────────
if not exist ".env" (
  echo [..] Creating .env file...

  if exist "backend\.env.example" (
    copy /Y "backend\.env.example" ".env" >nul
    echo [OK]  .env created from backend\.env.example
  ) else (
    (
      echo # AI Content Factory -- Environment Variables
      echo APP_ENV=development
      echo FRONTEND_URL=http://localhost:3000
      echo.
      echo # Database
      echo POSTGRES_PASSWORD=password
      echo DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/ai_content_factory
      echo DATABASE_URL_SYNC=postgresql://postgres:password@postgres:5432/ai_content_factory
      echo.
      echo # Redis
      echo REDIS_URL=redis://redis:6379/0
      echo CELERY_BROKER_URL=redis://redis:6379/0
      echo CELERY_RESULT_BACKEND=redis://redis:6379/1
      echo.
      echo # Security -- replace with random 64-char hex string
      echo SECRET_KEY=changeme-replace-with-random-64-char-hex
      echo ALGORITHM=HS256
      echo ACCESS_TOKEN_EXPIRE_MINUTES=1440
      echo.
      echo # Google OAuth [REQUIRED] -- https://console.cloud.google.com
      echo GOOGLE_CLIENT_ID=
      echo GOOGLE_CLIENT_SECRET=
      echo GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback
      echo.
      echo # YouTube API [REQUIRED]
      echo YOUTUBE_API_KEY=
      echo.
      echo # Groq AI -- PRIMARY free tier [REQUIRED] -- https://console.groq.com/keys
      echo GROQ_API_KEY=
      echo GROQ_MODEL=llama-3.3-70b-versatile
      echo.
      echo # OpenRouter -- Fallback [REQUIRED] -- https://openrouter.ai/keys
      echo OPENROUTER_API_KEY=
      echo OPENROUTER_MODEL=google/gemini-2.0-flash-001
      echo OPENROUTER_FALLBACK_MODEL=openai/gpt-4o-mini
      echo.
      echo # Whisper (GPU transcription)
      echo WHISPER_MODEL=large-v3
      echo WHISPER_DEVICE=cuda
      echo WHISPER_COMPUTE_TYPE=float16
      echo.
      echo # ACRCloud [REQUIRED] -- https://console.acrcloud.com
      echo ACRCLOUD_HOST=
      echo ACRCLOUD_ACCESS_KEY=
      echo ACRCLOUD_ACCESS_SECRET=
      echo.
      echo # Telegram Bot [REQUIRED]
      echo TELEGRAM_BOT_TOKEN=
      echo TELEGRAM_CHAT_ID=
      echo.
      echo # SendGrid [REQUIRED] -- https://app.sendgrid.com/settings/api_keys
      echo SENDGRID_API_KEY=
      echo FROM_EMAIL=noreply@yourdomain.com
      echo.
      echo # Storage
      echo STORAGE_TYPE=local
      echo LOCAL_STORAGE_PATH=./storage
    ) > ".env"
    echo [OK]  .env created
  )

  echo [!!] IMPORTANT: Fill in required API keys in .env before using the pipeline!
) else (
  echo [OK]  .env already exists -- skipping
)

:: ── 3. Create storage directories ────────────────────────────────────────────
echo [..] Creating storage directories...
if not exist "storage\videos"       mkdir "storage\videos"
if not exist "storage\clips"        mkdir "storage\clips"
if not exist "storage\thumbnails"   mkdir "storage\thumbnails"
if not exist "storage\audio_samples" mkdir "storage\audio_samples"
echo [OK]  Storage directories ready

:: ── 4. Reset volumes if requested ────────────────────────────────────────────
if "%RESET_DB%"=="true" (
  echo [!!] Resetting DB volumes (--reset flag)...
  docker compose down -v 2>nul
  echo [OK]  Volumes removed
)

:: ── 5. Build Docker images ────────────────────────────────────────────────────
echo.
echo [..] Building Docker images...
echo      First run takes 5-10 min (downloads PyTorch CUDA ~1GB + ffmpeg static binary)
echo.
echo      Build notes:
echo      - Base: python:3.12-bullseye (Debian 11 stable)
echo      - bullseye-updates DISABLED to avoid CDN hash mismatch (Apr 2026)
echo      - ffmpeg: static binary from BtbN/FFmpeg-Builds (no apt install)
echo      - psycopg2-binary: pre-compiled wheel (no gcc/libpq-dev needed)
echo      - PyTorch cu124: from download.pytorch.org (auto-fallback to CPU)
echo.

docker compose build backend celery_worker frontend
if errorlevel 1 (
  echo [ERR] Docker build failed! Check output above for errors.
  pause & exit /b 1
)
echo.
echo [OK]  All Docker images built

:: ── 6. Start services ────────────────────────────────────────────────────────
echo.
echo [..] Starting all services...
docker compose up -d
if errorlevel 1 (
  echo [ERR] docker compose up failed!
  echo       Common fix: stop conflicting containers using ports 5432, 6379, 8000, 3000
  docker compose ps
  pause & exit /b 1
)
echo.

:: ── 7. Wait for Postgres + Redis ─────────────────────────────────────────────
echo [..] Waiting for Postgres to be ready...
set /a TRIES=0
:WAIT_PG
set /a TRIES+=1
if %TRIES% gtr 30 (
  echo [ERR] Postgres did not become healthy after 60s
  pause & exit /b 1
)
docker compose exec -T postgres pg_isready -U postgres >nul 2>&1
if errorlevel 1 (
  timeout /t 2 /nobreak >nul
  goto WAIT_PG
)
echo [OK]  Postgres healthy

echo [..] Waiting for Redis to be ready...
set /a TRIES=0
:WAIT_REDIS
set /a TRIES+=1
if %TRIES% gtr 15 (
  echo [ERR] Redis did not become healthy after 30s
  pause & exit /b 1
)
docker compose exec -T redis redis-cli ping 2>nul | findstr /C:"PONG" >nul
if errorlevel 1 (
  timeout /t 2 /nobreak >nul
  goto WAIT_REDIS
)
echo [OK]  Redis healthy

:: ── 8. Run database migrations ────────────────────────────────────────────────
echo.
echo [..] Running Alembic migrations...
docker compose exec -T backend alembic upgrade head
if errorlevel 1 (
  echo [ERR] Migrations failed! Check backend logs: docker compose logs backend
  pause & exit /b 1
)
echo [OK]  Migrations complete (001 -> 008)

:: ── 9. Install frontend dependencies ─────────────────────────────────────────
where npm >nul 2>&1
if not errorlevel 1 (
  if exist "frontend" (
    if not exist "frontend\node_modules" (
      echo.
      echo [..] Installing frontend npm dependencies...
      pushd frontend
      npm install --legacy-peer-deps
      if errorlevel 1 (
        echo [!!] npm install failed -- frontend dev mode won't work
      ) else (
        echo [OK]  Frontend dependencies installed
      )
      popd
    ) else (
      echo [OK]  frontend\node_modules already exists -- skipping npm install
    )
  )
)

:: ── 10. Print summary ─────────────────────────────────────────────────────────
echo.
echo ============================================================
echo    Setup Complete!
echo ============================================================
echo.
echo   Services:
docker compose ps --format "  {{.Name}}: {{.Status}}" 2>nul
echo.
echo   Access Points:
echo     Backend API:       http://localhost:8000
echo     API Docs:          http://localhost:8000/docs
echo     Frontend (Docker): http://localhost:3000
echo     Celery Flower:     http://localhost:5555
echo.
echo   To start frontend in dev mode (hot reload):
echo     cd frontend ^&^& npm run dev
echo.
echo   Useful commands:
echo     docker compose logs -f backend          (Backend logs)
echo     docker compose logs -f celery_worker    (Worker logs)
echo     docker compose exec backend alembic upgrade head
echo     docker compose down                     (Stop all)
echo     setup.bat --reset                       (Wipe DB + restart)
echo.
echo   Next steps:
echo     1. Fill in API keys in .env
echo        (GROQ_API_KEY, OPENROUTER_API_KEY, GOOGLE_CLIENT_ID, etc.)
echo     2. Configure Google OAuth:
echo        https://console.cloud.google.com
echo     3. Add redirect URI: http://localhost:3000/auth/callback
echo     4. cd frontend ^&^& npm run dev
echo.

pause
