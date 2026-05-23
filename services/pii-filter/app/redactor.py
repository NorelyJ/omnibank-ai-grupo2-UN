"""Redactor — the gRPC-facing entry point.

Wires the detector and the policy engine: detect PII, then apply the block/redact
policy. `source` ("user_input" or "tool_result") is carried for metrics labeling.
"""

import time

from app import metrics
from app.detector import detect
from app.policy import PolicyContext, apply_policy


def _is_own_name(entity, given_name: str) -> bool:
    return (
        entity.type == "PER"
        and given_name != ""
        and entity.original.strip().casefold() == given_name.strip().casefold()
    )


def redact(text: str, source: str, given_name: str) -> tuple[str, str, str]:
    """Return (redacted_text, decision, warning_message).

    decision is "REDACT" (text was scrubbed, possibly a no-op) or "BLOCK" (the
    request must be rejected — it contained a card number).
    """
    start = time.perf_counter()
    entities = detect(text)
    result = apply_policy(text, entities, PolicyContext(given_name=given_name))

    if result.decision == "BLOCK":
        for entity in entities:
            if entity.type == "CARD":
                metrics.pii_blocked_total.labels(entity_type=entity.type).inc()
    else:
        for entity in entities:
            if _is_own_name(entity, given_name):
                continue
            metrics.pii_redactions_total.labels(entity_type=entity.type, source=source).inc()

    metrics.pii_filter_duration_seconds.labels(source=source).observe(time.perf_counter() - start)
    return result.text, result.decision, result.warning
