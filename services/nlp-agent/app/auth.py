"""In-agent Cognito JWT validator — the fallback auth path.

Primary auth is Kong's `jwt` plugin (it validates the token at the gateway and
injects identity headers). This module is the documented fallback for when Kong's
OSS JWT plugin cannot cleanly validate Cognito tokens: the agent verifies the access
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
    """Verify a Cognito ACCESS token and return its claims.

    Access tokens carry `token_use: "access"` and `client_id` (no `aud`). The
    customer identity (`bank_customer_id`, `given_name`) is injected by the Cognito
    Pre-Token-Generation Lambda. Raises InvalidToken on any failure.
    """
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        key = next((k for k in _get_jwks().get("keys", []) if k["kid"] == kid), None)
        if key is None:
            raise InvalidToken("token signed by an unknown key")
        claims = jwt.decode(token, key, algorithms=["RS256"], options={"verify_aud": False})
    except JWTError as exc:
        raise InvalidToken(str(exc)) from exc
    if claims.get("token_use") != "access":
        raise InvalidToken("not an access token")
    if claims.get("client_id") != COGNITO_CLIENT_ID:
        raise InvalidToken("token issued for a different client")
    return claims
