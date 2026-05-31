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
_ISSUER_URL = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST"
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
    monkeypatch.setattr(auth, "_ISSUER", _ISSUER_URL)
    monkeypatch.setattr(auth, "_get_jwks", lambda: _jwks)


def test_valid_access_token_returns_claims(monkeypatch):
    _setup(monkeypatch)
    token = _make_token(
        {
            "token_use": "access",
            "client_id": _CLIENT_ID,
            "iss": _ISSUER_URL,
            "exp": int(time.time()) + 3600,
            "bank_customer_id": "CUST-001",
            "given_name": "Juan",
        }
    )
    claims = auth.validate_token(token)
    assert claims["bank_customer_id"] == "CUST-001"
    assert claims["given_name"] == "Juan"


def test_id_typed_token_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token(
        {"token_use": "id", "client_id": _CLIENT_ID, "exp": int(time.time()) + 3600}
    )
    try:
        auth.validate_token(token)
        raise AssertionError("an ID-typed token must be rejected on the access-token path")
    except auth.InvalidToken:
        pass


def test_wrong_client_id_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token(
        {"token_use": "access", "client_id": "some-other-app", "exp": int(time.time()) + 3600}
    )
    try:
        auth.validate_token(token)
        raise AssertionError("a token for another client_id must be rejected")
    except auth.InvalidToken:
        pass


def test_expired_token_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token(
        {"token_use": "access", "client_id": _CLIENT_ID, "exp": int(time.time()) - 10}
    )
    try:
        auth.validate_token(token)
        raise AssertionError("expired token should have been rejected")
    except auth.InvalidToken:
        pass


def test_tampered_token_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token(
        {"token_use": "access", "client_id": _CLIENT_ID, "exp": int(time.time()) + 3600}
    )
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    try:
        auth.validate_token(tampered)
        raise AssertionError("tampered token should have been rejected")
    except auth.InvalidToken:
        pass


def test_wrong_issuer_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token(
        {
            "token_use": "access",
            "client_id": _CLIENT_ID,
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_EVIL",
            "exp": int(time.time()) + 3600,
        }
    )
    try:
        auth.validate_token(token)
        raise AssertionError("a token from a different issuer must be rejected")
    except auth.InvalidToken:
        pass


def test_missing_token_use_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token(
        {"client_id": _CLIENT_ID, "iss": _ISSUER_URL, "exp": int(time.time()) + 3600}
    )
    try:
        auth.validate_token(token)
        raise AssertionError("a token with no token_use must be rejected")
    except auth.InvalidToken:
        pass


def test_missing_client_id_is_rejected(monkeypatch):
    _setup(monkeypatch)
    token = _make_token({"token_use": "access", "iss": _ISSUER_URL, "exp": int(time.time()) + 3600})
    try:
        auth.validate_token(token)
        raise AssertionError("a token with no client_id must be rejected")
    except auth.InvalidToken:
        pass
