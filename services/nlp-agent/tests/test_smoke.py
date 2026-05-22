"""Slice 1 smoke tests for nlp-agent.

These tests do NOT call OpenAI. They cover:
- The HTTP surface (/health, /version)
- The dev escape-hatch resolution
- The production safety guard (SKIP_JWT + ENV=production must exit non-zero)

End-to-end chat verification is the acceptance-criteria curl test, which requires a
real OPENAI_API_KEY and is run via `docker compose up`.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-used-in-smoke")

from app.config import assert_safety_or_exit  # noqa: E402
from app.main import _resolve_customer, app  # noqa: E402

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_version_returns_git_sha():
    response = client.get("/version")
    assert response.status_code == 200
    assert "git_sha" in response.json()


def test_chat_without_customer_id_returns_401(monkeypatch):
    monkeypatch.setattr("app.main.SKIP_JWT", False)
    response = client.post("/v1/chat", json={"message": "hola"})
    assert response.status_code == 401


def test_resolve_customer_prefers_header():
    cid, name = _resolve_customer("CUST-042", "María")
    assert cid == "CUST-042"
    assert name == "María"


def test_resolve_customer_falls_back_to_dev_env(monkeypatch):
    monkeypatch.setattr("app.main.SKIP_JWT", True)
    monkeypatch.setattr("app.main.DEV_CUSTOMER", "CUST-001")
    monkeypatch.setattr("app.main.DEV_GIVEN_NAME", "Juan")
    cid, name = _resolve_customer(None, None)
    assert cid == "CUST-001"
    assert name == "Juan"


def test_safety_guard_exits_when_skip_jwt_and_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SKIP_JWT_VALIDATION", "true")
    with pytest.raises(SystemExit) as excinfo:
        assert_safety_or_exit()
    assert excinfo.value.code == 2


def test_safety_guard_allows_dev_with_skip_jwt(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("SKIP_JWT_VALIDATION", "true")
    assert_safety_or_exit()  # should not raise


def test_safety_guard_allows_production_with_jwt(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("SKIP_JWT_VALIDATION", "false")
    assert_safety_or_exit()  # should not raise
