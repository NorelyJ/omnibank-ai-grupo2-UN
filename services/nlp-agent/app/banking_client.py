import os

import httpx

MOCK_BANKING_URL = os.getenv("MOCK_BANKING_URL", "http://mock-core-banking:8001")


async def get_accounts(customer_id: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            f"{MOCK_BANKING_URL}/v1/customers/me/accounts",
            headers={"X-Bank-Customer-Id": customer_id},
        )
        response.raise_for_status()
        return response.json()
