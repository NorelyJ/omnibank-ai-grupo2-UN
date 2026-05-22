"""Integration tests for mock-core-banking through its HTTP surface.

Every test drives the public API with a TestClient — no internal state is touched.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["customers_loaded"] == 3


def test_version_returns_git_sha():
    response = client.get("/version")
    assert response.status_code == 200
    assert "git_sha" in response.json()


def test_accounts_requires_header():
    assert client.get("/v1/customers/me/accounts").status_code == 400


def test_unknown_customer_returns_404():
    response = client.get("/v1/customers/me/accounts", headers={"X-Bank-Customer-Id": "CUST-999"})
    assert response.status_code == 404


def test_profile_for_each_user_differs():
    juan = client.get("/v1/customers/me", headers={"X-Bank-Customer-Id": "CUST-001"}).json()
    maria = client.get("/v1/customers/me", headers={"X-Bank-Customer-Id": "CUST-002"}).json()
    carlos = client.get("/v1/customers/me", headers={"X-Bank-Customer-Id": "CUST-003"}).json()
    assert juan["first_name"] == "Juan"
    assert maria["first_name"] == "María"
    assert carlos["first_name"] == "Carlos"


def test_balances_differ_between_users():
    def savings_balance(customer_id: str) -> int:
        body = client.get(
            "/v1/customers/me/accounts", headers={"X-Bank-Customer-Id": customer_id}
        ).json()
        return next(a["balance_cop"] for a in body["accounts"] if a["type"] == "savings")

    assert savings_balance("CUST-001") != savings_balance("CUST-002")
    assert savings_balance("CUST-002") != savings_balance("CUST-003")


def test_transactions_default_limit_is_five():
    body = client.get(
        "/v1/customers/me/transactions", headers={"X-Bank-Customer-Id": "CUST-001"}
    ).json()
    assert len(body["transactions"]) == 5


def test_transactions_respect_explicit_limit():
    body = client.get(
        "/v1/customers/me/transactions?limit=2", headers={"X-Bank-Customer-Id": "CUST-001"}
    ).json()
    assert len(body["transactions"]) == 2


def test_transactions_limit_capped_at_twenty():
    body = client.get(
        "/v1/customers/me/transactions?limit=500", headers={"X-Bank-Customer-Id": "CUST-001"}
    ).json()
    assert len(body["transactions"]) <= 20


def test_transactions_filtered_by_account():
    body = client.get(
        "/v1/customers/me/transactions?account_id=COR-001&limit=20",
        headers={"X-Bank-Customer-Id": "CUST-001"},
    ).json()
    assert body["transactions"]
    assert all(t["account_id"] == "COR-001" for t in body["transactions"])


def test_products_catalog_lists_all_four_types():
    body = client.get("/v1/products").json()
    types = {p["product_type"] for p in body["products"]}
    assert types == {"credit_card", "savings", "mortgage", "loan"}
