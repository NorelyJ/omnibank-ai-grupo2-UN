SHELL := /bin/bash
SERVICES := nlp-agent pii-filter mock-core-banking

.PHONY: help dev down logs test lint format install-dev

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start the full local stack (docker compose up --build)
	docker compose up --build

down: ## Stop and remove containers
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f

install-dev: ## Create a venv per service and install dev dependencies
	@for svc in $(SERVICES); do \
		echo "→ $$svc"; \
		(cd services/$$svc && python3.12 -m venv .venv && .venv/bin/pip install --quiet -r requirements-dev.txt); \
	done

test: ## Run pytest in every service (uses each service's .venv)
	@set -e; for svc in $(SERVICES); do \
		echo "→ pytest $$svc"; \
		(cd services/$$svc && .venv/bin/pytest); \
	done

lint: ## Run ruff check + ruff format --check on every service
	@set -e; for svc in $(SERVICES); do \
		echo "→ ruff $$svc"; \
		(cd services/$$svc && .venv/bin/ruff check . && .venv/bin/ruff format --check .); \
	done

format: ## Auto-format every service with ruff
	@for svc in $(SERVICES); do \
		(cd services/$$svc && .venv/bin/ruff format .); \
	done
