# OmniBank AI — Conversational Agent

PII-protected conversational agent for OmniBank. University project, DevOps & SRE UNAL 2026.

- **PRD:** issue [#1](https://github.com/NorelyJ/omnibank-ai-grupo2-UN/issues/1)
- **Slice 1 (scaffold):** issue [#2](https://github.com/NorelyJ/omnibank-ai-grupo2-UN/issues/2)
- **Slice 2 (PII filter):** issue [#6](https://github.com/NorelyJ/omnibank-ai-grupo2-UN/issues/6)

## Repo layout

```
services/
  nlp-agent/          FastAPI agent — OpenAI function calling, /v1/chat
  pii-filter/         gRPC PII redactor (Slice 1: stub) + FastAPI sidecar
  mock-core-banking/  FastAPI mock bank data, hardcoded JSON
infra/
  terraform/          AWS infrastructure (Slice 4)
  helm/               Kubernetes Helm charts (Slice 6)
docker-compose.yml    Local dev stack
Makefile              dev / test / lint / format
.env.example          Template — copy to .env, fill in OPENAI_API_KEY
```

Each service has its own `requirements.{in,txt}`, `requirements-dev.txt`, `Dockerfile`, `pyproject.toml`.

## Local development

### Prerequisites
- Python 3.12
- Docker + Docker Compose v2
- An OpenAI API key (gpt-4o-mini access)

### First-time setup

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

make install-dev   # per-service venvs + dev deps
```

### Daily workflow

```bash
make dev      # docker compose up --build — full stack with hot-reload
make test     # pytest in every service
make lint     # ruff check + ruff format --check
make format   # auto-format with ruff
make down     # stop & remove containers
make help     # show all targets
```

### Smoke check

With the stack running:

```bash
curl http://localhost:8001/health   # mock-core-banking
curl http://localhost:8002/health   # pii-filter
curl http://localhost:8000/health   # nlp-agent

curl -X POST http://localhost:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "¿cuál es mi saldo?"}'
```

The chat endpoint is hardcoded in local dev to act as customer `CUST-001` (Juan) via the `DEV_USER_BANK_CUSTOMER_ID` env var. Slice 3 expands this to Juan + María + Carlos.

### Dev escape hatches

Two env vars allow direct curl testing without standing up Cognito/Kong locally:
- `SKIP_JWT_VALIDATION=true` — skip JWT validation, trust env-var customer ID
- `DEV_USER_BANK_CUSTOMER_ID=CUST-001` — which customer the request is "logged in as"

**The agent refuses to start (`exit 2`) if `SKIP_JWT_VALIDATION=true` AND `ENV=production`.** This prevents a misconfigured Helm value from silently disabling auth in a deployed environment.

## What's built so far

**Slice 1 — scaffold**
- Monorepo scaffold, three minimal services, docker-compose, Makefile, tests, lint.
- One OpenAI function-calling tool (`get_my_accounts`).
- One hardcoded customer (Juan / `CUST-001`).

**Slice 2 — PII filter**
- Real hybrid PII detector: regex (cédula, NIT with check digit, Colombian mobile,
  email, account, Luhn-validated card, IPv4/IPv6) + spaCy `es_core_news_md` NER
  (person, location, organization).
- Redaction policy engine: card numbers BLOCK the request; everything else is
  redacted to `[TIPO]` placeholders; the authenticated user's own first name
  passes through.
- nlp-agent scrubs every user message through the filter before the LLM, and
  fails safe (no LLM call) if the filter is unreachable.

Still stubbed: Redis history (Slice 3), JWT validation (Slice 7).

See issues [#2 — #13](https://github.com/NorelyJ/omnibank-ai-grupo2-UN/issues) for the full slice plan.
