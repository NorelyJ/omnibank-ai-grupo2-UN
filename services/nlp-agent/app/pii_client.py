"""gRPC client for the pii-filter service.

Hides the gRPC stub, the 200ms timeout, and the fail-safe contract: if the filter
is unreachable or slow, `redact` raises `PiiFilterUnavailable` so the caller can
refuse to reach the LLM rather than silently bypass redaction.
"""

import os
from dataclasses import dataclass

import grpc

from app import pii_pb2, pii_pb2_grpc

PII_FILTER_GRPC = os.getenv("PII_FILTER_GRPC", "pii-filter:50051")
PII_TIMEOUT_SECONDS = 0.2

_channel: grpc.aio.Channel | None = None
_stub: pii_pb2_grpc.PiiFilterStub | None = None


class PiiFilterUnavailable(Exception):
    """The PII filter could not be reached or did not respond in time."""


@dataclass(frozen=True)
class RedactResult:
    text: str
    decision: str  # "REDACT" or "BLOCK"
    warning: str


def _stub_for_channel() -> pii_pb2_grpc.PiiFilterStub:
    global _channel, _stub
    if _stub is None:
        _channel = grpc.aio.insecure_channel(PII_FILTER_GRPC)
        _stub = pii_pb2_grpc.PiiFilterStub(_channel)
    return _stub


async def redact(text: str, source: str, given_name: str) -> RedactResult:
    """Scrub `text` through the pii-filter. Raises PiiFilterUnavailable on failure."""
    try:
        response = await _stub_for_channel().Redact(
            pii_pb2.RedactRequest(text=text, source=source, given_name=given_name),
            timeout=PII_TIMEOUT_SECONDS,
        )
    except grpc.aio.AioRpcError as exc:
        raise PiiFilterUnavailable(f"pii-filter RPC failed: {exc.code()}") from exc
    return RedactResult(
        text=response.text,
        decision=response.decision,
        warning=response.warning_message,
    )
