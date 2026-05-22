SHELL := /bin/bash
SERVICES := nlp-agent pii-filter mock-core-banking

HELM_DIR     := infra/helm
KIND_CLUSTER := omnibank
COMPOSE_PROJECT := omnibank-ai-grupo2-un

.PHONY: help dev down logs test lint format install-dev \
        helm-lint kind-up kind-load kind-down deploy-local install-kps

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

# --- Helm / kind --------------------------------------------------------------

helm-lint: ## helm lint all four charts
	@set -e; for c in nlp-agent pii-filter mock-core-banking omnibank; do \
		echo "→ helm lint $$c"; \
		helm lint $(HELM_DIR)/$$c; \
	done

kind-up: ## Create the kind cluster with Calico, metrics-server and the ServiceMonitor CRD
	kind create cluster --name $(KIND_CLUSTER) --config infra/kind/kind-config.yaml
	kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.28.2/manifests/calico.yaml
	kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
	kubectl -n kube-system patch deployment metrics-server --type=json \
		-p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
	kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.76.0/example/prometheus-operator-crd/monitoring.coreos.com_servicemonitors.yaml
	@echo "kind cluster '$(KIND_CLUSTER)' ready."

kind-load: ## Build the service images and load them into the kind cluster
	docker compose build
	@for svc in $(SERVICES); do \
		docker tag $(COMPOSE_PROJECT)-$$svc omnibank-$$svc:dev; \
		kind load docker-image omnibank-$$svc:dev --name $(KIND_CLUSTER); \
	done

kind-down: ## Delete the kind cluster
	kind delete cluster --name $(KIND_CLUSTER)

deploy-local: kind-load ## Deploy the umbrella chart to the kind cluster
	helm dependency update $(HELM_DIR)/omnibank
	helm upgrade --install omnibank $(HELM_DIR)/omnibank \
		-f $(HELM_DIR)/omnibank/values-dev.yaml --wait --timeout 120s
	@echo "omnibank deployed — port-forward with: kubectl port-forward svc/nlp-agent 8000:8000"

install-kps: ## Install kube-prometheus-stack + the OmniBank Grafana dashboard
	kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
	helm repo update prometheus-community
	# Apply the operator CRDs server-side, adopting the ServiceMonitor CRD that
	# kind-up already installed; then install the chart with --skip-crds.
	helm show crds prometheus-community/kube-prometheus-stack \
		| kubectl apply --server-side --force-conflicts -f -
	@GRAFANA_PW=$$(aws secretsmanager get-secret-value --secret-id omnibank/grafana-admin \
		--query SecretString --output text 2>/dev/null || echo "omnibank-admin"); \
	helm upgrade --install kps prometheus-community/kube-prometheus-stack \
		--namespace monitoring -f $(HELM_DIR)/kps-values.yaml \
		--set grafana.adminPassword=$$GRAFANA_PW \
		--skip-crds --wait --timeout 600s
	kubectl apply -f infra/observability/grafana-dashboard.yaml
	@echo "kube-prometheus-stack installed."
	@echo "Grafana: kubectl -n monitoring port-forward svc/kps-grafana 3000:80"
