"""Custom Prometheus metrics for mock-core-banking.

Registered on the default registry, so they appear on the same `/metrics` endpoint
that prometheus-fastapi-instrumentator exposes. No label carries a customer ID.
"""

from prometheus_client import Counter, Histogram

banking_requests_total = Counter(
    "omnibank_banking_requests_total",
    "Core-banking requests by endpoint and HTTP status",
    ["endpoint", "status"],
)

banking_duration_seconds = Histogram(
    "omnibank_banking_duration_seconds",
    "Core-banking request duration in seconds",
)
