"""Slice 1 stub redactor.

Returns input text unchanged. Slice 2 replaces this with the real regex + spaCy
hybrid implementation and the redaction policy engine.
"""


def redact(text: str, source: str, given_name: str) -> tuple[str, str, str]:
    """Return (redacted_text, decision, warning_message). Stub: pass-through."""
    return text, "REDACT", ""
