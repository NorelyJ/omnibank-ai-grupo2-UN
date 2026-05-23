# Demo dry run 1 — notes

Dry run 1 is a HITL deliverable: the full 15-minute demo, all three devs present,
no audience, following the script in the PRD's Q17a. Record surprises here and fix
them before grading day.

## Demo script (15 min)

1. `make dev` — local stack up; the four intents via curl.
2. PII demo — cédula redacted, card number blocked (no LLM call).
3. Fail-safe — `docker compose stop pii-filter`, show the "no disponible" reply.
4. `terraform apply` recap + `make deploy-eks` on EKS.
5. `make get-token USER=juan|maria` — multi-user isolation via Kong/NLB.
6. Grafana "OmniBank Chat Overview" — PII redactions panel spikes live.
7. ArgoCD UI — the `omnibank` Application synced from git.

## Surprises found

_(fill in during the dry run — each surprise gets a line and a fix/owner)_

- …

## Status

- [ ] Dry run 1 completed
- [ ] All surprises fixed
