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

clean:
	$(HEADER)
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@find . -name "*.pyc" -delete 2>/dev/null; true
	@find . -name "*.tmp" -delete 2>/dev/null; true
	@echo -e "$(GREEN)Cleaned up!$(RESET)"
