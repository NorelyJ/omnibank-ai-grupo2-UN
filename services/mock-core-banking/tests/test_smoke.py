from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_accounts_requires_header():
    response = client.get("/v1/customers/me/accounts")
    assert response.status_code == 400


def test_accounts_for_known_customer():
    response = client.get(
        "/v1/customers/me/accounts",
        headers={"X-Bank-Customer-Id": "CUST-001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["customer_id"] == "CUST-001"
    assert body["accounts"][0]["account_id"] == "AHO-001"


def test_accounts_for_unknown_customer():
    response = client.get(
        "/v1/customers/me/accounts",
        headers={"X-Bank-Customer-Id": "CUST-999"},
    )
    assert response.status_code == 404
