"""In-agent Cognito JWT validator — the fallback auth path.

Primary auth is Kong's `jwt` plugin (it validates the token at the gateway and
injects identity headers). This module is the documented fallback for when Kong's
OSS JWT plugin cannot cleanly validate Cognito tokens: the agent verifies the ID
token itself against Cognito's JWKS, with the JWKS cached in-process.
"""

import os
import time

import httpx
from jose import jwt
from jose.exceptions import JWTError

COGNITO_JWKS_URL = os.getenv("COGNITO_JWKS_URL", "")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")
_JWKS_TTL_SECONDS = 3600

_jwks_cache: dict | None = None
_jwks_fetched_at = 0.0


class InvalidToken(Exception):
    """The presented JWT failed signature, expiry, audience or issuer validation."""


def _get_jwks() -> dict:
    """Return Cognito's JWKS, cached in-process for an hour."""
    global _jwks_cache, _jwks_fetched_at
    if _jwks_cache is None or time.time() - _jwks_fetched_at > _JWKS_TTL_SECONDS:
        response = httpx.get(COGNITO_JWKS_URL, timeout=5.0)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_fetched_at = time.time()
    return _jwks_cache


def validate_token(token: str) -> dict:
    """Verify a Cognito ID token and return its claims.

    Raises InvalidToken if the signature, expiry or audience does not check out.
    """
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        key = next((k for k in _get_jwks().get("keys", []) if k["kid"] == kid), None)
        if key is None:
            raise InvalidToken("token signed by an unknown key")
        return jwt.decode(token, key, algorithms=["RS256"], audience=COGNITO_CLIENT_ID)
    except JWTError as exc:
        raise InvalidToken(str(exc)) from exc
