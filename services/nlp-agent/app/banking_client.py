"""HTTP client for mock-core-banking.

Customer identity travels in the `X-Bank-Customer-Id` header — never in the URL.
Calls raise `httpx.HTTPError` on failure; the tool dispatcher turns that into a
graceful error result for the LLM.
"""

import os

import httpx

MOCK_BANKING_URL = os.getenv("MOCK_BANKING_URL", "http://mock-core-banking:8001")
_TIMEOUT = 5.0


def _headers(customer_id: str) -> dict[str, str]:
    return {"X-Bank-Customer-Id": customer_id}


async def get_customer(customer_id: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            f"{MOCK_BANKING_URL}/v1/customers/me", headers=_headers(customer_id)
        )
        response.raise_for_status()
        return response.json()


async def get_accounts(customer_id: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            f"{MOCK_BANKING_URL}/v1/customers/me/accounts", headers=_headers(customer_id)
        )
        response.raise_for_status()
        return response.json()


async def get_transactions(customer_id: str, account_id: str | None = None, limit: int = 5) -> dict:
    params: dict[str, object] = {"limit": limit}
    if account_id:
        params["account_id"] = account_id
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(
            f"{MOCK_BANKING_URL}/v1/customers/me/transactions",
            headers=_headers(customer_id),
            params=params,
        )
        response.raise_for_status()
        return response.json()


async def list_products() -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(f"{MOCK_BANKING_URL}/v1/products")
        response.raise_for_status()
        return response.json()


async def list_faq() -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.get(f"{MOCK_BANKING_URL}/v1/faq")
        response.raise_for_status()
        return response.json()
