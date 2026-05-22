import os

from fastapi import FastAPI, Header, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from app.config import assert_safety_or_exit, env_bool
from app.llm import chat

# Enforced at module load so a misconfigured pod fails fast at startup.
assert_safety_or_exit()

GIT_SHA = os.getenv("GIT_SHA", "dev")
SKIP_JWT = env_bool("SKIP_JWT_VALIDATION", default=False)
DEV_CUSTOMER = os.getenv("DEV_USER_BANK_CUSTOMER_ID")
DEV_GIVEN_NAME = os.getenv("DEV_USER_GIVEN_NAME", "Juan")

app = FastAPI(title="omnibank-nlp-agent", version=GIT_SHA)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict:
    return {"git_sha": GIT_SHA}


def _resolve_customer(
    header_customer_id: str | None, header_given_name: str | None
) -> tuple[str, str]:
    """Return (customer_id, given_name) — from JWT-injected headers, or dev fallbacks."""
    if header_customer_id:
        return header_customer_id, header_given_name or "Cliente"
    if SKIP_JWT and DEV_CUSTOMER:
        return DEV_CUSTOMER, DEV_GIVEN_NAME
    raise HTTPException(status_code=401, detail="Missing X-Bank-Customer-Id header")


@app.post("/v1/chat", response_model=ChatResponse)
async def chat_endpoint(
    body: ChatRequest,
    x_bank_customer_id: str | None = Header(default=None),
    x_user_given_name: str | None = Header(default=None),
) -> ChatResponse:
    customer_id, given_name = _resolve_customer(x_bank_customer_id, x_user_given_name)
    reply = await chat(body.message, customer_id=customer_id, given_name=given_name)
    return ChatResponse(reply=reply)
