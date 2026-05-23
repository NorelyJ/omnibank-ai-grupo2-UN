"""Custom Prometheus metrics for pii-filter.

Registered on the default registry, so they appear on the FastAPI sidecar's
`/metrics` endpoint. Labels carry entity types and the call source only — never a
customer identifier.
"""

from prometheus_client import Counter, Histogram

pii_redactions_total = Counter(
    "omnibank_pii_redactions_total",
    "PII entities redacted, by type and call source",
    ["entity_type", "source"],
)

pii_blocked_total = Counter(
    "omnibank_pii_blocked_total",
    "Requests blocked outright, by the entity type that triggered the block",
    ["entity_type"],
)

pii_filter_duration_seconds = Histogram(
    "omnibank_pii_filter_duration_seconds",
    "Time spent detecting + applying the redaction policy",
    ["source"],
)
