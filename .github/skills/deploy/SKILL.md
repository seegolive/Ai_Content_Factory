---
name: deploy
description: "CI/CD and deployment skill for this project. Use when: setting up GitHub Actions workflows, automating Docker builds, configuring deployment pipelines, adding auto-test-on-push, or deploying to a VPS/cloud server. Covers GitHub Actions, Docker Compose deployment, secret management, and rollback strategy."
argument-hint: "e.g. 'setup GitHub Actions CI', 'auto deploy on push to main', 'add test pipeline'"
---

# Deploy / CI-CD Skill

## When to Use
- Setting up GitHub Actions for automated testing, building, or deployment
- Configuring auto-deploy on push to `main`
- Adding Docker build + push to registry
- Deploying to a remote VPS with Docker Compose
- Managing deployment secrets securely

## Project Deployment Context

```
Stack:
  - Backend: FastAPI in Docker (python:3.12-slim)
  - Frontend: Next.js in Docker (node:22-slim, standalone output)
  - Workers: Celery in Docker (same image as backend)
  - DB: PostgreSQL (Docker volume)
  - Cache/Queue: Redis (Docker volume)

GPU: NVIDIA RTX 4070 — required for Celery worker (faster-whisper CUDA)
     On CI/CD: GPU not available, skip GPU tests, use CPU fallback

Current: Manual `make dev` / `make dev-build`
Target: GitHub Actions CI + optional auto-deploy
```

## Procedure

### 1. Read Context
- Read `docker-compose.yml` to understand service structure
- Read `Makefile` for existing commands
- Read `backend/requirements.txt` for Python deps
- Read `frontend/package.json` for Node deps
- Read `.env.example` for required secrets

### 2. GitHub Actions CI (Test on Push)

File: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: ai_content_factory_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: |
          cd ai-content-factory/backend
          pip install -r requirements.txt

      - name: Run tests
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/ai_content_factory_test
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: test-secret-key-not-for-production
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          cd ai-content-factory/backend
          pytest tests/ -x -q --tb=short

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: ai-content-factory/frontend/package-lock.json

      - name: Install & Build
        run: |
          cd ai-content-factory/frontend
          npm ci
          npm run build
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000
```

### 3. Auto-Deploy to VPS (Optional)

File: `.github/workflows/deploy.yml`

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /home/deploy/Ai_Content_Factory/ai-content-factory
            git pull origin main
            make dev-build
```

### 4. Required GitHub Secrets

Set these in GitHub → Settings → Secrets → Actions:

| Secret | Value |
|--------|-------|
| `OPENROUTER_API_KEY` | OpenRouter API key (for AI tests) |
| `VPS_HOST` | IP/domain of deployment server |
| `VPS_USER` | SSH username on server |
| `VPS_SSH_KEY` | Private SSH key (PEM format) |

**Never commit `.env` to git.** Use secrets only.

### 5. Rollback Strategy

```bash
# On VPS: rollback to previous commit
git log --oneline -5          # find commit hash
git checkout <commit-hash>    # rollback
make dev-build                # redeploy
```

Or via git:
```bash
git revert HEAD --no-edit
git push origin main          # triggers auto-deploy
```

## Anti-patterns to Avoid
- Don't put real API keys in workflow YAML files
- Don't skip `npm ci` (use `ci` not `install` for reproducible builds)
- Don't deploy without running tests first
- Don't use `latest` Docker image tags in production (pin versions)
