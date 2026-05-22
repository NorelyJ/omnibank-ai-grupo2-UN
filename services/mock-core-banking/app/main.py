import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

DATA_FILE = Path(__file__).parent.parent / "data" / "customers.json"
CUSTOMERS: dict = json.loads(DATA_FILE.read_text(encoding="utf-8"))

app = FastAPI(title="omnibank-mock-core-banking", version=os.getenv("GIT_SHA", "dev"))
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "customers_loaded": len(CUSTOMERS)}


def _require_customer(customer_id: str | None) -> dict:
    if not customer_id:
        raise HTTPException(status_code=400, detail="X-Bank-Customer-Id header required")
    customer = CUSTOMERS.get(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"Unknown customer {customer_id}")
    return customer


@app.get("/v1/customers/me/accounts")
def get_my_accounts(x_bank_customer_id: str | None = Header(default=None)) -> dict:
    customer = _require_customer(x_bank_customer_id)
    return {"customer_id": customer["customer_id"], "accounts": customer["accounts"]}
