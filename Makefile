SHELL := /bin/bash
SERVICES := nlp-agent pii-filter mock-core-banking

HELM_DIR     := infra/helm
TF_DIR       := infra/terraform
KIND_CLUSTER := omnibank
COMPOSE_PROJECT := omnibank-ai-grupo2-un

.PHONY: help dev down logs test lint format install-dev \
        helm-lint kind-up kind-load kind-down deploy-local install-kps \
        install-kong deploy-eks get-token install-logging install-argocd

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

# --- EKS deploy + Kong --------------------------------------------------------

install-kong: ## Install Kong API Gateway (DBless) in front of the agent
	kubectl create configmap kong-declarative \
		--from-file=kong.yml=infra/kong/kong-declarative.yaml \
		--dry-run=client -o yaml | kubectl apply -f -
	helm repo add kong https://charts.konghq.com
	helm repo update kong
	helm upgrade --install kong kong/kong -f $(HELM_DIR)/kong-values.yaml --wait --timeout 300s
	@echo "Kong installed. NLB DNS: kubectl get svc kong-kong-proxy -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'"

deploy-eks: ## Deploy the full stack to EKS (keyless Bedrock via IRSA + Helm)
	helm dependency update $(HELM_DIR)/omnibank
	@echo "→ deploying umbrella chart with Terraform-derived endpoints + IRSA role..."
	@cd $(TF_DIR) && \
	REDIS=$$(terraform output -raw redis_endpoint) && \
	JWKS=$$(terraform output -raw cognito_jwks_url) && \
	CLIENT=$$(terraform output -raw cognito_client_id) && \
	ROLE=$$(terraform output -raw nlp_agent_irsa_role_arn) && \
	cd $(CURDIR) && \
	helm upgrade --install omnibank $(HELM_DIR)/omnibank \
		-f $(HELM_DIR)/omnibank/values-prod.yaml \
		--set global.imageTag=$$(git rev-parse --short HEAD) \
		--set nlp-agent.serviceAccount.roleArn=$$ROLE \
		--set nlp-agent.config.REDIS_URL=redis://$$REDIS:6379 \
		--set nlp-agent.config.COGNITO_JWKS_URL=$$JWKS \
		--set nlp-agent.config.COGNITO_CLIENT_ID=$$CLIENT \
		--wait --timeout 600s
	@echo "deploy-eks done."

get-token: ## Print a Cognito ID token. Usage: make get-token USER=juan|maria|carlos
	@case "$(USER)" in juan|maria|carlos) ;; \
		*) echo "Usage: make get-token USER=juan|maria|carlos"; exit 1;; esac
	@cd $(TF_DIR) && CLIENT=$$(terraform output -raw cognito_client_id) && cd $(CURDIR) && \
	aws cognito-idp initiate-auth --auth-flow USER_PASSWORD_AUTH --region us-east-1 \
		--client-id $$CLIENT \
		--auth-parameters USERNAME=$(USER)@omnibank.demo,PASSWORD=Demo1234! \
		--query 'AuthenticationResult.AccessToken' --output text

install-logging: ## Install the FluentBit DaemonSet shipping container logs to CloudWatch
	helm repo add eks https://aws.github.io/eks-charts
	helm repo update eks
	@cd $(TF_DIR) && ROLE=$$(terraform output -raw fluentbit_irsa_role_arn) && cd $(CURDIR) && \
	helm upgrade --install aws-for-fluent-bit eks/aws-for-fluent-bit \
		--namespace kube-system -f $(HELM_DIR)/fluentbit-values.yaml \
		--set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$$ROLE \
		--wait --timeout 300s
	@echo "FluentBit installed — logs shipping to CloudWatch group /aws/eks/omnibank"

install-argocd: ## Install ArgoCD and the omnibank Application (demo cluster, week 3)
	kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo update argo
	helm upgrade --install argocd argo/argo-cd --namespace argocd \
		-f $(HELM_DIR)/argocd-values.yaml --wait --timeout 300s
	kubectl apply -f infra/argocd/omnibank-application.yaml
	@echo "ArgoCD installed. UI: kubectl -n argocd port-forward svc/argocd-server 8080:80"
	@echo "Admin password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"

# --- Cost discipline (monthly budget cap — override BUDGET_CAP) ----------------
CLUSTER    := omnibank-eks
REGION     := us-east-1
BUDGET_CAP := 100

.PHONY: stop-night start-day destroy-all budget-check

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

budget-check: ## Print month-to-date AWS spend against the monthly budget cap
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
		if (pct > 70) print "WARNING: over 70% of the monthly budget cap!"; \
	}'
