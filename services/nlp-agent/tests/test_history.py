"""Tests for the Redis conversation-history client.

The behavior that matters most is the fail-safe contract: a Redis outage must
never break a chat turn. The Redis boundary is mocked so these run without a
live Redis.
"""

from app import history


class _BrokenRedis:
    async def get(self, *args, **kwargs):
        raise ConnectionError("redis unreachable")

    async def set(self, *args, **kwargs):
        raise ConnectionError("redis unreachable")


async def test_load_returns_empty_when_redis_unreachable(monkeypatch):
    monkeypatch.setattr(history, "_redis", lambda: _BrokenRedis())
    assert await history.load("CUST-001") == []


async def test_append_does_not_raise_when_redis_unreachable(monkeypatch):
    monkeypatch.setattr(history, "_redis", lambda: _BrokenRedis())
    # Must complete silently — history is best-effort.
    await history.append("CUST-001", "hola", "respuesta redactada")
