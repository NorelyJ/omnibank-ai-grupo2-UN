"""Safety tests for the chat orchestrator.

These verify the two fail-safe paths required by the PRD: a card number and an
unreachable PII filter must both stop the turn BEFORE any Bedrock call. Only the
external boundaries (pii-filter, Bedrock) are mocked.
"""

import os

os.environ.setdefault("AWS_REGION", "us-east-1")

from app import llm  # noqa: E402
from app.pii_client import PiiFilterUnavailable, RedactResult  # noqa: E402


def _fail_if_called():
    raise AssertionError("Bedrock must not be reached on a short-circuited turn")


async def test_card_block_returns_warning_without_calling_bedrock(monkeypatch):
    async def fake_redact(text, source, given_name):
        return RedactResult(text="", decision="BLOCK", warning="No compartas tu tarjeta por chat.")

    monkeypatch.setattr(llm, "pii_redact", fake_redact)
    monkeypatch.setattr(llm, "client", _fail_if_called)

    reply = await llm.chat("mi tarjeta 4532015112830366", customer_id="CUST-001", given_name="Juan")
    assert reply == "No compartas tu tarjeta por chat."


async def test_filter_unavailable_returns_safe_message_without_calling_bedrock(monkeypatch):
    async def fake_redact(text, source, given_name):
        raise PiiFilterUnavailable("pii-filter down")

    monkeypatch.setattr(llm, "pii_redact", fake_redact)
    monkeypatch.setattr(llm, "client", _fail_if_called)

    reply = await llm.chat("¿cuál es mi saldo?", customer_id="CUST-001", given_name="Juan")
    assert reply == llm.FILTER_UNAVAILABLE_MSG
