"""OpenAI client + agent loop.

Every user message is scrubbed by the pii-filter before it reaches the LLM, and
every tool result is scrubbed before it is added to the LLM context. The loop is
bounded to MAX_ITERATIONS (defense against runaway tool-call cycles).
"""

import datetime as dt
import json
import logging
import os

import httpx
from openai import AsyncOpenAI

from app.banking_client import get_accounts, get_transactions, list_products
from app.history import append as history_append
from app.history import load as history_load
from app.pii_client import PiiFilterUnavailable
from app.pii_client import redact as pii_redact

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_ITERATIONS = 3

# Shown when the PII filter is unreachable — the agent fails safe and never calls
# the LLM with un-scrubbed text.
FILTER_UNAVAILABLE_MSG = (
    "El asistente no está disponible temporalmente. Por favor intenta de nuevo en unos minutos."
)

logger = logging.getLogger("nlp-agent.llm")

_client: AsyncOpenAI | None = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_my_accounts",
            "description": "Obtiene las cuentas del cliente autenticado con sus saldos actuales.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_my_transactions",
            "description": "Lista las transacciones recientes del cliente, opcionalmente "
            "filtradas por cuenta.",
            "parameters": {
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
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_info",
            "description": "Obtiene información de un producto bancario de OmniBank.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_type": {
                        "type": "string",
                        "enum": ["credit_card", "savings", "mortgage", "loan"],
                    }
                },
                "required": ["product_type"],
            },
        },
    },
]


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
    try:
        if name == "get_my_accounts":
            return json.dumps(await get_accounts(customer_id))
        if name == "list_my_transactions":
            limit = args.get("limit") or 5
            return json.dumps(await get_transactions(customer_id, args.get("account_id"), limit))
        if name == "get_product_info":
            catalog = await list_products()
            product_type = args.get("product_type")
            info = next((p for p in catalog["products"] if p["product_type"] == product_type), None)
            return json.dumps(info or {"error": f"producto desconocido: {product_type}"})
        return json.dumps({"error": f"herramienta desconocida: {name}"})
    except httpx.HTTPError as exc:
        logger.warning("banking call failed for tool %s: %s", name, exc)
        return json.dumps({"error": "banking_unavailable"})


async def _redact_tool_result(raw_result: str, given_name: str) -> str:
    """Scrub a tool result before it enters the LLM context. Raises if filter is down."""
    filtered = await pii_redact(raw_result, source="tool_result", given_name=given_name)
    return filtered.text


async def chat(user_message: str, customer_id: str, given_name: str) -> str:
    """Handle one chat turn: scrub PII, load history, run the agent loop, persist.

    Card numbers and an unreachable filter both short-circuit before any LLM call.
    """
    try:
        filtered = await pii_redact(user_message, source="user_input", given_name=given_name)
    except PiiFilterUnavailable:
        return FILTER_UNAVAILABLE_MSG

    if filtered.decision == "BLOCK":
        return filtered.warning

    history = await history_load(customer_id)
    try:
        reply = await _run_agent_loop(filtered.text, history, customer_id, given_name)
    except PiiFilterUnavailable:
        return FILTER_UNAVAILABLE_MSG

    await _store_history(customer_id, filtered.text, reply, given_name)
    if filtered.warning:
        return f"{filtered.warning}\n\n{reply}"
    return reply


async def _run_agent_loop(
    user_message: str, history: list[dict], customer_id: str, given_name: str
) -> str:
    messages: list[dict] = [{"role": "system", "content": system_prompt(given_name)}]
    messages += [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": user_message})

    for _ in range(MAX_ITERATIONS):
        response = await client().chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )
        msg = response.choices[0].message
        if not msg.tool_calls:
            return msg.content or ""

        # Append the assistant's tool-call message, then dispatch each call.
        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            raw = await _invoke_tool(tc.function.name, args, customer_id)
            safe = await _redact_tool_result(raw, given_name)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": safe})

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
