"""Redis-backed conversation history.

One rolling conversation per customer (`conversation:{customer_id}`), capped at
MAX_MESSAGES with a 24h TTL refreshed on every write. Redis is best-effort: if it
is unreachable, `load` returns an empty history and `append` is a no-op — a cache
hiccup must never break a chat turn.

Only PII-redacted text is ever stored here; callers pass already-scrubbed content.
"""

import datetime as dt
import json
import logging
import os

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
HISTORY_TTL_SECONDS = 86400  # 24h
MAX_MESSAGES = 20  # 10 user + 10 assistant

logger = logging.getLogger("nlp-agent.history")

_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


def _key(customer_id: str) -> str:
    return f"conversation:{customer_id}"


async def load(customer_id: str) -> list[dict]:
    """Return the stored conversation, or [] if Redis is unreachable."""
    try:
        raw = await _redis().get(_key(customer_id))
    except Exception as exc:  # noqa: BLE001 — best-effort cache, never fail the turn
        logger.warning("Redis load failed, continuing without history: %s", exc)
        return []
    return json.loads(raw) if raw else []


async def append(customer_id: str, user_content: str, assistant_content: str) -> None:
    """Append one user+assistant pair, trim to MAX_MESSAGES, refresh the TTL."""
    now = dt.datetime.now(dt.UTC).isoformat()
    try:
        history = await load(customer_id)
        history.append({"role": "user", "content": user_content, "ts": now})
        history.append({"role": "assistant", "content": assistant_content, "ts": now})
        history = history[-MAX_MESSAGES:]
        await _redis().set(_key(customer_id), json.dumps(history), ex=HISTORY_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001 — best-effort cache, never fail the turn
        logger.warning("Redis append failed, history not persisted: %s", exc)
