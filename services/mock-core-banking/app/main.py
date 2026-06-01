"""Mock core-banking service.

Customer data is loaded once from JSON baked into the image. Customer identity
always comes from the `X-Bank-Customer-Id` header — never from the URL path.
"""

import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from prometheus_fastapi_instrumentator import Instrumentator

from app import metrics

DATA_DIR = Path(__file__).parent.parent / "data"
CUSTOMERS: dict = json.loads((DATA_DIR / "customers.json").read_text(encoding="utf-8"))
PRODUCTS: dict = json.loads((DATA_DIR / "products.json").read_text(encoding="utf-8"))
FAQ: dict = json.loads((DATA_DIR / "faq.json").read_text(encoding="utf-8"))

GIT_SHA = os.getenv("GIT_SHA", "dev")
DEFAULT_TXN_LIMIT = 5
MAX_TXN_LIMIT = 20

app = FastAPI(title="omnibank-mock-core-banking", version=GIT_SHA)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.middleware("http")
async def _record_metrics(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    metrics.banking_duration_seconds.observe(time.perf_counter() - start)
    metrics.banking_requests_total.labels(
        endpoint=request.url.path, status=str(response.status_code)
    ).inc()
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "customers_loaded": len(CUSTOMERS)}


@app.get("/version")
def version() -> dict:
    return {"git_sha": GIT_SHA}


def _require_customer(customer_id: str | None) -> dict:
    if not customer_id:
        raise HTTPException(status_code=400, detail="X-Bank-Customer-Id header required")
    customer = CUSTOMERS.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Unknown customer {customer_id}")
    return customer


@app.get("/v1/customers/me")
def get_me(x_bank_customer_id: str | None = Header(default=None)) -> dict:
    customer = _require_customer(x_bank_customer_id)
    return {
        "customer_id": customer["customer_id"],
        "first_name": customer["first_name"],
        "last_name": customer["last_name"],
        "email": customer["email"],
    }


@app.get("/v1/customers/me/accounts")
def get_my_accounts(x_bank_customer_id: str | None = Header(default=None)) -> dict:
    customer = _require_customer(x_bank_customer_id)
    return {"customer_id": customer["customer_id"], "accounts": customer["accounts"]}


@app.get("/v1/customers/me/transactions")
def get_my_transactions(
    x_bank_customer_id: str | None = Header(default=None),
    account_id: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_TXN_LIMIT, ge=1),
) -> dict:
    customer = _require_customer(x_bank_customer_id)
    txns = customer["transactions"]
    if account_id:
        txns = [t for t in txns if t["account_id"] == account_id]
    txns = sorted(txns, key=lambda t: t["date"], reverse=True)
    return {
        "customer_id": customer["customer_id"],
        "transactions": txns[: min(limit, MAX_TXN_LIMIT)],
    }


@app.get("/v1/products")
def get_products() -> dict:
    return {"products": list(PRODUCTS.values())}


@app.get("/v1/faq")
def get_faq() -> dict:
    return {"faq": list(FAQ.values())}
