# Demo Q&A — rehearsed answers

Answers to the adversarial questions for demo dry run 2. Keep them short and
concrete; point at code/config when asked.

### "What happens if Redis dies mid-chat?"

Nothing breaks. Redis holds **conversation history only**, and the history client
(`nlp-agent/app/history.py`) is best-effort: `load()` catches any connection error
and returns an empty history; `append()` catches and is a silent no-op. The chat
turn still completes — the user just loses multi-turn memory for that turn. Proven
by `test_history.py` and a live `docker compose stop redis` check.

### "Where is my cédula actually stored?"

Nowhere in plaintext. The cédula is detected by pii-filter and replaced with a
`[CÉDULA]` placeholder **before** the message reaches the LLM or Redis. Redis only
ever receives the redacted form. Prometheus labels never contain identifiers. The
cédula exists only in the original HTTP request body in memory for the few
milliseconds before redaction — it is never logged, persisted, or sent to the LLM (AWS Bedrock).

### "How do you know the PII filter actually ran?"

Three independent signals: (1) the `omnibank_pii_redactions_total` Prometheus
counter increments per entity type — visible on the Grafana dashboard; (2) the
agent **fails safe** — if the filter is unreachable it returns "no disponible" and
never calls Bedrock (`test_chat_safety.py`); (3) the filter has a 31-test suite
covering every detector pattern and every policy path. The filter is on the
critical path — the agent cannot reach Bedrock without going through it.

### "How does the agent authenticate to the model — is there a key to rotate?"

There is no API key. The agent calls Claude Haiku on **AWS Bedrock** and is
authenticated by **IRSA**: in EKS the pod's ServiceAccount assumes a scoped IAM
role (`bedrock:InvokeModel` on the Claude Haiku ARNs only) and AWS issues
short-lived credentials automatically — nothing long-lived is stored, so there is
no key to leak or rotate. Locally the agent uses the developer's AWS credential
chain. Spend is bounded by the model choice (Haiku) and can be capped with AWS
Budgets / Cost Explorer alerts.

### "What happens if AWS Academy credentials expire mid-deploy?"

AWS Academy sessions last 4 hours. `terraform apply` and `make deploy-eks` are
human-triggered with fresh credentials precisely so an expiry never breaks an
automated pipeline (CI deliberately does **not** deploy). If credentials expire
mid-`apply`, Terraform state is consistent — re-run `apply` with new credentials
and it continues from where it stopped.

### "Your NetworkPolicies — are they actually enforced?"

Yes on the kind cluster (Calico is installed by `make kind-up`) — verified live: a
pod in another namespace cannot reach `pii-filter`, while an nlp-agent pod can. On
EKS, enforcement depends on the cluster's CNI policy mode; the policies are always
declared so the zero-trust intent is explicit and review-able regardless.

### "What stops the agent from leaking PII in its own reply?"

The system prompt forbids echoing full cédula/account/card numbers, and the LLM
only ever sees redacted input, so it has nothing to leak. The assistant reply is
also re-scrubbed before being written to Redis. A post-LLM scan of the user-facing
reply is listed as a production gap.
