SHELL := /bin/bash

# Color codes
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RESET := \033[0m

define HEADER
@echo -e "$(CYAN)"
@echo -e "  ╔═══════════════════════════════════════╗"
@echo -e "  ║   🏭  AI CONTENT FACTORY             ║"
@echo -e "  ║   Automated Video → Clips Pipeline   ║"
@echo -e "  ╚═══════════════════════════════════════╝"
@echo -e "$(RESET)"
endef

.PHONY: setup dev down logs logs-worker migrate makemigrations shell-backend shell-db test lint format redis-cli flower install-whisper clean

setup:
	$(HEADER)
	@echo -e "$(GREEN)Setting up AI Content Factory...$(RESET)"
	@[ -f .env ] || cp .env.example .env && echo "Created .env from .env.example"
	@cd frontend && npm install
	@echo -e "$(GREEN)Setup complete! Run 'make dev' to start.$(RESET)"

dev:
	$(HEADER)
	@docker compose up -d

dev-build:
	$(HEADER)
	@echo -e "$(CYAN)Building frontend image with latest code...$(RESET)"
	@docker compose build frontend
	@docker compose up -d
	@echo -e "$(GREEN)All services started with latest frontend.$(RESET)"

down:
	@docker compose down

logs:
	@docker compose logs -f

logs-worker:
	@docker compose logs -f celery_worker

migrate:
	$(HEADER)
	@docker compose exec backend alembic upgrade head

makemigrations:
	$(HEADER)
	@read -p "Migration name: " name; \
	docker compose exec backend alembic revision --autogenerate -m "$$name"

shell-backend:
	@docker compose exec backend bash

shell-db:
	@docker compose exec postgres psql -U postgres -d ai_content_factory

test:
	$(HEADER)
	@docker compose exec backend pytest -v

lint:
	$(HEADER)
	@cd backend && ruff check . && mypy app/

format:
	$(HEADER)
	@cd backend && black . && isort .

redis-cli:
	@docker compose exec redis redis-cli

flower:
	@echo "Opening Flower at http://localhost:5555"
	@xdg-open http://localhost:5555 2>/dev/null || open http://localhost:5555 2>/dev/null || true

install-whisper:
	$(HEADER)
	@echo -e "$(YELLOW)Downloading faster-whisper large-v3 model...$(RESET)"
	@docker compose exec celery_worker python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cpu')"
	@echo -e "$(GREEN)Model downloaded!$(RESET)"

install-torch:
	$(HEADER)
	@echo -e "$(YELLOW)Installing PyTorch with CUDA 12.4 (RTX 4070)...$(RESET)"
	@docker compose exec celery_worker pip install torch==2.5.1+cu124 torchaudio==2.5.1+cu124 \
		--index-url https://download.pytorch.org/whl/cu124
	@echo -e "$(GREEN)PyTorch CUDA installed!$(RESET)"

gpu-test:
	$(HEADER)
	@echo -e "$(YELLOW)Testing CUDA + GPU availability...$(RESET)"
	@docker compose exec celery_worker python -c "\
import torch; \
print('CUDA available:', torch.cuda.is_available()); \
print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'); \
print('VRAM:', round(torch.cuda.get_device_properties(0).total_memory/1e9, 1), 'GB' if torch.cuda.is_available() else ''); \
"
	@echo -e "$(GREEN)GPU test complete!$(RESET)"

ai-test:
	$(HEADER)
	@echo -e "$(YELLOW)Testing all 3 AI providers...$(RESET)"
	@docker compose exec backend python -c "\
import asyncio, time, os, httpx; \
\
async def test_provider(name, base_url, api_key, model): \
    start = time.perf_counter(); \
    try: \
        async with httpx.AsyncClient(base_url=base_url, headers={'Authorization': f'Bearer {api_key}'}, timeout=30) as c: \
            r = await c.post('/chat/completions', json={'model': model, 'messages': [{'role': 'user', 'content': 'Reply with JSON: {\"ok\": true}'}], 'max_tokens': 20, 'response_format': {'type': 'json_object'}}); \
            r.raise_for_status(); \
        status = '✅ OK'; \
    except Exception as e: \
        status = f'❌ {str(e)[:40]}'; \
    latency = round((time.perf_counter() - start) * 1000); \
    return (name, model, status, latency); \
\
async def main(): \
    from app.core.config import settings; \
    providers = [ \
        ('Groq', settings.GROQ_BASE_URL, settings.GROQ_API_KEY, settings.GROQ_MODEL), \
        ('OpenRouter Gemini', settings.OPENROUTER_BASE_URL, settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL), \
        ('OpenRouter GPT-4o-mini', settings.OPENROUTER_BASE_URL, settings.OPENROUTER_API_KEY, settings.OPENROUTER_FALLBACK_MODEL), \
    ]; \
    results = await asyncio.gather(*[test_provider(*p) for p in providers]); \
    print(); \
    print(f'  {\"Provider\":<28} {\"Model\":<35} {\"Status\":<12} Latency'); \
    print('  ' + '-'*90); \
    for name, model, status, latency in results: \
        print(f'  {name:<28} {model:<35} {status:<12} {latency}ms'); \
    print(); \
\
asyncio.run(main()) \
"
	@echo -e "$(GREEN)AI provider test complete!$(RESET)"

clean:
	$(HEADER)
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@find . -name "*.pyc" -delete 2>/dev/null; true
	@find . -name "*.tmp" -delete 2>/dev/null; true
	@echo -e "$(GREEN)Cleaned up!$(RESET)"
