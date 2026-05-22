"""OpenAI client + agent loop.

Every user message is scrubbed by the pii-filter before it reaches the LLM. The
loop is bounded to MAX_ITERATIONS (defense against runaway tool-call cycles).
"""

import datetime as dt
import json
import os

from openai import AsyncOpenAI

from app.banking_client import get_accounts
from app.pii_client import PiiFilterUnavailable
from app.pii_client import redact as pii_redact

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_ITERATIONS = 3

# Shown when the PII filter is unreachable — the agent fails safe and never calls
# the LLM with un-scrubbed text.
FILTER_UNAVAILABLE_MSG = (
    "El asistente no está disponible temporalmente. " "Por favor intenta de nuevo en unos minutos."
)

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
            "description": "Obtiene todas las cuentas del cliente autenticado con saldos actuales.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
]


def system_prompt(given_name: str) -> str:
    today = dt.date.today().isoformat()
    return (
        'Eres "Omni", el asistente virtual de OmniBank. Hablas con clientes reales del banco.\n\n'
        "REGLAS:\n"
        "- Responde en español, claro y conciso (máx 3 oraciones).\n"
        "- Si el cliente escribe en inglés, responde en inglés.\n"
        "- Usa el nombre del cliente para personalizar el saludo inicial.\n"
        "- Para consultas de saldo, USA la herramienta disponible. NUNCA inventes datos.\n"
        "- NO realizas transferencias ni pagos. Si te piden eso, indica que deben usar la "
        "app móvil o llamar al *777.\n"
        "- NO repitas números de cédula, cuentas completas, o tarjetas.\n"
        "- Si una herramienta falla, discúlpate y sugiere intentar más tarde.\n\n"
        f"Cliente autenticado: {given_name}\n"
        f"Fecha actual: {today}\n"
    )


async def _invoke_tool(name: str, customer_id: str) -> str:
    if name == "get_my_accounts":
        return json.dumps(await get_accounts(customer_id))
    return json.dumps({"error": f"Unknown tool {name}"})


async def chat(user_message: str, customer_id: str, given_name: str) -> str:
    """Handle one chat turn: scrub PII, run the agent loop, return the reply.

    Card numbers and an unreachable filter both short-circuit before any LLM call.
    """
    try:
        filtered = await pii_redact(user_message, source="user_input", given_name=given_name)
    except PiiFilterUnavailable:
        return FILTER_UNAVAILABLE_MSG

    if filtered.decision == "BLOCK":
        return filtered.warning

    reply = await _run_agent_loop(filtered.text, customer_id, given_name)
    if filtered.warning:
        return f"{filtered.warning}\n\n{reply}"
    return reply


async def _run_agent_loop(user_message: str, customer_id: str, given_name: str) -> str:
    messages: list[dict] = [
        {"role": "system", "content": system_prompt(given_name)},
        {"role": "user", "content": user_message},
    ]

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
            result = await _invoke_tool(tc.function.name, customer_id)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return "Lo siento, no pude completar tu consulta en este momento."
