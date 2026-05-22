"""Tests for the in-agent Cognito JWT validator (the Kong fallback path).

A throwaway RSA keypair stands in for Cognito's signing key, so these run fully
offline — no Cognito, no network.
"""

import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app import auth

_CLIENT_ID = "test-client-id"
_KID = "test-key-1"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_private_pem = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
_public_pem = (
    _private_key.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)
_jwks = {"keys": [{**jwk.construct(_public_pem, "RS256").to_dict(), "kid": _KID}]}


def _make_token(claims: dict) -> str:
    return jwt.encode(claims, _private_pem, algorithm="RS256", headers={"kid": _KID})


def _setup(monkeypatch):
    monkeypatch.setattr(auth, "COGNITO_CLIENT_ID", _CLIENT_ID)
    monkeypatch.setattr(auth, "_get_jwks", lambda: _jwks)


def test_valid_token_returns_claims(monkeypatch):
    _setup(monkeypatch)
    token = _make_token(
        {
            "aud": _CLIENT_ID,
            "exp": int(time.time()) + 3600,
            "custom:bank_customer_id": "CUST-001",
            "given_name": "Juan",
        }
    )
    claims = auth.validate_token(token)
    assert claims["custom:bank_customer_id"] == "CUST-001"
    assert claims["given_name"] == "Juan"


def test_expired_token_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token({"aud": _CLIENT_ID, "exp": int(time.time()) - 10})
    try:
        auth.validate_token(token)
        raise AssertionError("expired token should have been rejected")
    except auth.InvalidToken:
        pass


def test_wrong_audience_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token({"aud": "some-other-app", "exp": int(time.time()) + 3600})
    try:
        auth.validate_token(token)
        raise AssertionError("token for another audience should have been rejected")
    except auth.InvalidToken:
        pass


def test_tampered_token_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token({"aud": _CLIENT_ID, "exp": int(time.time()) + 3600})
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    try:
        auth.validate_token(tampered)
        raise AssertionError("tampered token should have been rejected")
    except auth.InvalidToken:
        pass
