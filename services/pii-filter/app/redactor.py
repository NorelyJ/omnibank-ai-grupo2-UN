"""Redactor — the gRPC-facing entry point.

Wires the detector and the policy engine: detect PII, then apply the block/redact
policy. `source` ("user_input" or "tool_result") is carried for metrics labeling.
"""

from app.detector import detect
from app.policy import PolicyContext, apply_policy


def redact(text: str, source: str, given_name: str) -> tuple[str, str, str]:
    """Return (redacted_text, decision, warning_message).

    decision is "REDACT" (text was scrubbed, possibly a no-op) or "BLOCK" (the
    request must be rejected — it contained a card number).
    """
    entities = detect(text)
    result = apply_policy(text, entities, PolicyContext(given_name=given_name))
    return result.text, result.decision, result.warning
