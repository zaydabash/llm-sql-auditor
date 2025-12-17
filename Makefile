.PHONY: help install install-dev test test-cov lint format clean dev docker-up docker-down docker-build

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -r requirements.txt

install-dev: ## Install development dependencies
	pip install -r requirements.txt pytest pytest-cov pytest-asyncio ruff black mypy

test: ## Run tests
	python3 -m pytest backend/tests/ -v

test-cov: ## Run tests with coverage report
	python3 -m pytest backend/tests/ --cov=backend --cov-report=term-missing --cov-report=html

test-watch: ## Run tests in watch mode
	python3 -m pytest backend/tests/ -v --maxfail=1 -x

lint: ## Run linters (ruff, mypy)
	ruff check backend/
	mypy backend/ --config-file=mypy.ini

format: ## Format code with black and ruff
	black backend/
	ruff check --fix backend/

clean: ## Clean build artifacts and cache
	rm -rf __pycache__ .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -f demo.db audit_history.db

dev: ## Start development servers (backend + frontend)
	@echo "Starting development servers..."
	@./scripts/dev_up.sh

dev-backend: ## Start backend only
	python3 -m uvicorn backend.app:app --reload --port 8000

dev-frontend: ## Start frontend only
	cd frontend && npm run dev

seed-db: ## Seed demo database
	@./scripts/seed_demo.sh

docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start Docker containers
	docker-compose up -d

docker-down: ## Stop Docker containers
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

docker-clean: ## Remove Docker containers and volumes
	docker-compose down -v
	docker system prune -f

verify: ## Run all verification checks
	@echo "Running verification checks..."
	@echo "\n1. Running tests..."
	@make test-cov
	@echo "\n2. Running linters..."
	@make lint
	@echo "\n3. Checking imports..."
	@python3 -c "from backend.services.pipeline import audit_queries; from backend.core.monitoring import metrics; print('✅ All imports work')"
	@echo "\n✅ All verification checks passed!"

ci: ## Run CI checks (tests + linting)
	@make test-cov
	@make lint
	@echo "✅ CI checks passed!"

setup: ## Initial setup (install deps, create .env, seed db)
	@echo "Setting up SQL Auditor..."
	@if [ ! -f .env ]; then cp .env.example .env && echo "✅ Created .env file"; fi
	@make install-dev
	@make seed-db
	@echo "✅ Setup complete! Run 'make dev' to start development servers"
