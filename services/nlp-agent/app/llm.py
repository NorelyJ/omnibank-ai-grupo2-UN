"""Bedrock Converse client + agent loop.

Every user message is scrubbed by the pii-filter before it reaches the LLM, and
every tool result is scrubbed before it is added to the LLM context. The loop is
bounded to MAX_ITERATIONS (defense against runaway tool-call cycles).
"""

import asyncio
import datetime as dt
import json
import logging
import os

import boto3
import httpx

from app import metrics
from app.banking_client import get_accounts, get_transactions, list_products
from app.history import append as history_append
from app.history import load as history_load
from app.pii_client import PiiFilterUnavailable
from app.pii_client import redact as pii_redact

MODEL = os.getenv("BEDROCK_MODEL_ID", "us.meta.llama4-maverick-17b-instruct-v1:0")
MAX_TOKENS = 1024
MAX_ITERATIONS = 3

# Shown when the PII filter is unreachable — the agent fails safe and never calls
# the LLM with un-scrubbed text.
FILTER_UNAVAILABLE_MSG = (
    "El asistente no está disponible temporalmente. Por favor intenta de nuevo en unos minutos."
)

logger = logging.getLogger("nlp-agent.llm")

_client = None


def client():
    global _client
    if _client is None:
        # No API key: SigV4 via the botocore credential chain (IRSA in EKS,
        # env/profile locally). Converse is provider-agnostic.
        _client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return _client


TOOLS = {
    "tools": [
        {
            "toolSpec": {
                "name": "get_my_accounts",
                "description": "Obtiene las cuentas del cliente autenticado con sus saldos "
                "actuales.",
                "inputSchema": {"json": {"type": "object", "properties": {}, "required": []}},
            }
        },
        {
            "toolSpec": {
                "name": "list_my_transactions",
                "description": "Lista las transacciones recientes del cliente, opcionalmente "
                "filtradas por cuenta.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "account_id": {
                                "type": "string",
                                "description": "ID de cuenta a filtrar, p. ej. AHO-001.",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Cuántas transacciones traer (1-20). Por defecto 5.",
                            },
                        },
                        "required": [],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "get_product_info",
                "description": "Obtiene información de un producto bancario de OmniBank.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "product_type": {
                                "type": "string",
                                "enum": ["credit_card", "savings", "mortgage", "loan"],
                            }
                        },
                        "required": ["product_type"],
                    }
                },
            }
        },
    ]
}


def system_prompt(given_name: str) -> str:
    today = dt.date.today().isoformat()
    return (
        'Eres "Omni", el asistente virtual de OmniBank. Hablas con clientes reales del banco.\n\n'
        "REGLAS:\n"
        "- Responde en español, claro y conciso (máx 3 oraciones).\n"
        "- Si el cliente escribe en inglés, responde en inglés.\n"
        "- Usa el nombre del cliente para personalizar el saludo inicial.\n"
        "- Para consultas de cuentas, transacciones o productos, USA las herramientas "
        "disponibles. NUNCA inventes datos.\n"
        "- Para preguntas generales (horarios, ubicaciones, etc.) responde con tu "
        "conocimiento, sin herramientas.\n"
        "- NO realizas transferencias ni pagos. Si te piden eso, indica que deben usar la "
        "app móvil o llamar al *777.\n"
        "- NO repitas números de cédula, cuentas completas, o tarjetas.\n"
        "- Si una herramienta falla, discúlpate y sugiere intentar más tarde.\n\n"
        f"Cliente autenticado: {given_name}\n"
        f"Fecha actual: {today}\n"
    )


async def _invoke_tool(name: str, args: dict, customer_id: str) -> str:
    """Dispatch one tool call to mock-core-banking. Banking errors become a result."""
    status = "success"
    try:
        if name == "get_my_accounts":
            result = json.dumps(await get_accounts(customer_id))
        elif name == "list_my_transactions":
            limit = args.get("limit") or 5
            result = json.dumps(await get_transactions(customer_id, args.get("account_id"), limit))
        elif name == "get_product_info":
            catalog = await list_products()
            product_type = args.get("product_type")
            info = next((p for p in catalog["products"] if p["product_type"] == product_type), None)
            result = json.dumps(info or {"error": f"producto desconocido: {product_type}"})
        else:
            result = json.dumps({"error": f"herramienta desconocida: {name}"})
            status = "error"
    except httpx.HTTPError as exc:
        logger.warning("banking call failed for tool %s: %s", name, exc)
        result = json.dumps({"error": "banking_unavailable"})
        status = "error"
    metrics.tool_calls_total.labels(tool_name=name, status=status).inc()
    return result


async def _redact_tool_result(raw_result: str, given_name: str) -> str:
    """Scrub a tool result before it enters the LLM context. Raises if filter is down."""
    filtered = await pii_redact(raw_result, source="tool_result", given_name=given_name)
    return filtered.text


async def chat(user_message: str, customer_id: str, given_name: str) -> str:
    """Handle one chat turn: scrub PII, load history, run the agent loop, persist.

    Card numbers and an unreachable filter both short-circuit before any LLM call.
    """
    metrics.chat_requests_total.inc()
    try:
        filtered = await pii_redact(user_message, source="user_input", given_name=given_name)
    except PiiFilterUnavailable:
        return FILTER_UNAVAILABLE_MSG

    if filtered.decision == "BLOCK":
        return filtered.warning

    history = await history_load(customer_id)
    metrics.redis_history_size.observe(len(history))
    try:
        reply = await _run_agent_loop(filtered.text, history, customer_id, given_name)
    except PiiFilterUnavailable:
        return FILTER_UNAVAILABLE_MSG

    await _store_history(customer_id, filtered.text, reply, given_name)
    if filtered.warning:
        return f"{filtered.warning}\n\n{reply}"
    return reply


def _text_from(content) -> str:
    """Join the text blocks of a Converse response message into one string."""
    return "".join(b["text"] for b in content if "text" in b).strip()


async def _run_agent_loop(
    user_message: str, history: list[dict], customer_id: str, given_name: str
) -> str:
    messages: list[dict] = [
        {"role": h["role"], "content": [{"text": h["content"]}]} for h in history
    ]
    messages.append({"role": "user", "content": [{"text": user_message}]})

    for _ in range(MAX_ITERATIONS):
        try:
            response = await asyncio.to_thread(
                client().converse,
                modelId=MODEL,
                system=[{"text": system_prompt(given_name)}],
                messages=messages,
                toolConfig=TOOLS,
                inferenceConfig={"maxTokens": MAX_TOKENS},
            )
        except Exception:
            metrics.llm_calls_total.labels(model=MODEL, status="error").inc()
            raise
        metrics.llm_calls_total.labels(model=MODEL, status="success").inc()
        metrics.record_llm_usage(response.get("usage"))

        assistant = response["output"]["message"]
        if response.get("stopReason") != "tool_use":
            return _text_from(assistant["content"])

        # Append the assistant turn verbatim, then answer each toolUse with a
        # toolResult in a single user message.
        messages.append(assistant)
        tool_results: list[dict] = []
        for block in assistant["content"]:
            tu = block.get("toolUse")
            if not tu:
                continue
            raw = await _invoke_tool(tu["name"], dict(tu.get("input") or {}), customer_id)
            safe = await _redact_tool_result(raw, given_name)
            tool_results.append(
                {"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"text": safe}]}}
            )
        messages.append({"role": "user", "content": tool_results})

    return "Lo siento, no pude completar tu consulta en este momento."


async def _store_history(
    customer_id: str, redacted_user_text: str, reply: str, given_name: str
) -> None:
    """Persist the turn. Only redacted text is stored; skip the write if it cannot be."""
    try:
        reply_filtered = await pii_redact(reply, source="tool_result", given_name=given_name)
    except PiiFilterUnavailable:
        logger.warning("could not redact reply for history; skipping write")
        return
    await history_append(customer_id, redacted_user_text, reply_filtered.text)
