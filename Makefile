SHELL := /bin/bash
SERVICES := nlp-agent pii-filter mock-core-banking

# AWS / infrastructure
TF_DIR  := infra/terraform
CLUSTER := omnibank-eks
REGION  := us-east-1
BUDGET_CAP := 100

.PHONY: help dev down logs test lint format install-dev \
        stop-night start-day destroy-all budget-check

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

# --- Cost discipline (AWS Academy $100 cap) -----------------------------------

stop-night: ## Weeknight: scale EKS nodes to 0 and destroy ElastiCache Redis
	@echo "→ scaling EKS node group to 0 desired/min..."
	@NG=$$(aws eks list-nodegroups --cluster-name $(CLUSTER) --region $(REGION) \
		--query 'nodegroups[0]' --output text); \
	aws eks update-nodegroup-config --cluster-name $(CLUSTER) --region $(REGION) \
		--nodegroup-name $$NG --scaling-config minSize=0,maxSize=6,desiredSize=0
	@echo "→ destroying ElastiCache Redis..."
	cd $(TF_DIR) && terraform destroy -target=aws_elasticache_cluster.redis -auto-approve
	@echo "stop-night done — control plane, VPC and Cognito remain up for a fast morning restart."

start-day: ## Morning: restore EKS nodes to 2 and recreate ElastiCache Redis
	@echo "→ scaling EKS node group back to 2 desired..."
	@NG=$$(aws eks list-nodegroups --cluster-name $(CLUSTER) --region $(REGION) \
		--query 'nodegroups[0]' --output text); \
	aws eks update-nodegroup-config --cluster-name $(CLUSTER) --region $(REGION) \
		--nodegroup-name $$NG --scaling-config minSize=2,maxSize=6,desiredSize=2
	@echo "→ recreating ElastiCache Redis..."
	cd $(TF_DIR) && terraform apply -target=aws_elasticache_cluster.redis -auto-approve
	@echo "start-day done."

destroy-all: ## Weekend: full terraform destroy (requires typing 'destroy' to confirm)
	@read -r -p "This destroys ALL OmniBank infrastructure. Type 'destroy' to confirm: " ans; \
	if [ "$$ans" != "destroy" ]; then echo "Aborted — nothing destroyed."; exit 1; fi
	cd $(TF_DIR) && terraform destroy -auto-approve

budget-check: ## Print month-to-date AWS spend against the $100 cap
	@start=$$(date -u +%Y-%m-01); \
	end=$$(date -u +%Y-%m-%d); \
	if [ "$$start" = "$$end" ]; then end=$$(date -u +%Y-%m-02); fi; \
	amount=$$(aws ce get-cost-and-usage \
		--time-period Start=$$start,End=$$end \
		--granularity MONTHLY --metrics UnblendedCost \
		--query 'ResultsByTime[0].Total.UnblendedCost.Amount' --output text); \
	awk -v a="$$amount" -v cap="$(BUDGET_CAP)" 'BEGIN { \
		pct = a / cap * 100; \
		printf "Spent $$%.2f of $$%.2f cap (%.0f%%)\n", a, cap, pct; \
		if (pct > 70) print "WARNING: over 70% of the AWS Academy budget cap!"; \
	}'
