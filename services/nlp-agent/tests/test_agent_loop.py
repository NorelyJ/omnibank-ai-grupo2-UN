"""Agent-loop tests with a mocked Bedrock Converse client.

Only the external boundaries (pii-filter, banking, history, the bedrock-runtime
client) are mocked. The fake `converse` is sync (the loop calls it via
asyncio.to_thread).
"""

from app import llm
from app.pii_client import RedactResult


def _text_msg(text):
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 10, "outputTokens": 5},
    }


def _tool_msg(tool_use_id, name, payload):
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"toolUse": {"toolUseId": tool_use_id, "name": name, "input": payload}}
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 20, "outputTokens": 8},
    }


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def converse(self, **kwargs):  # sync — invoked via asyncio.to_thread
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _passthrough_pii(monkeypatch):
    async def fake_redact(text, source, given_name):
        return RedactResult(text=text, decision="REDACT", warning="")

    monkeypatch.setattr(llm, "pii_redact", fake_redact)

    async def fake_load(customer_id):
        return []

    async def fake_append(customer_id, user_content, assistant_content):
        return None

    monkeypatch.setattr(llm, "history_load", fake_load)
    monkeypatch.setattr(llm, "history_append", fake_append)


async def test_plain_text_reply(monkeypatch):
    _passthrough_pii(monkeypatch)
    fake = _FakeClient([_text_msg("Hola, Juan.")])
    monkeypatch.setattr(llm, "client", lambda: fake)

    reply = await llm.chat("hola", customer_id="CUST-001", given_name="Juan")

    assert reply == "Hola, Juan."
    assert fake.calls[0]["system"] == [{"text": llm.system_prompt("Juan")}]
    assert fake.calls[0]["messages"][-1] == {"role": "user", "content": [{"text": "hola"}]}


async def test_tool_use_round_trip(monkeypatch):
    _passthrough_pii(monkeypatch)

    async def fake_get_accounts(customer_id):
        return {"accounts": [{"id": "AHO-001", "balance": 5432100}]}

    monkeypatch.setattr(llm, "get_accounts", fake_get_accounts)

    fake = _FakeClient(
        [
            _tool_msg("tu_1", "get_my_accounts", {}),
            _text_msg("Tu saldo es 5,432,100 COP."),
        ]
    )
    monkeypatch.setattr(llm, "client", lambda: fake)

    reply = await llm.chat("¿cuál es mi saldo?", customer_id="CUST-001", given_name="Juan")

    assert "5,432,100" in reply
    second = fake.calls[1]["messages"]
    assert any(m["role"] == "assistant" for m in second)
    asst = next(m for m in second if m["role"] == "assistant")
    assert any("toolUse" in b for b in asst["content"])
    results = [b for m in second for b in m["content"] if isinstance(b, dict) and "toolResult" in b]
    assert results and results[0]["toolResult"]["toolUseId"] == "tu_1"


async def test_max_iterations_exhaustion_returns_fallback(monkeypatch):
    _passthrough_pii(monkeypatch)

    async def fake_get_accounts(customer_id):
        return {"accounts": []}

    monkeypatch.setattr(llm, "get_accounts", fake_get_accounts)

    fake = _FakeClient(
        [_tool_msg(f"tu_{i}", "get_my_accounts", {}) for i in range(llm.MAX_ITERATIONS)]
    )
    monkeypatch.setattr(llm, "client", lambda: fake)

    reply = await llm.chat("dame todo", customer_id="CUST-001", given_name="Juan")

    assert reply == "Lo siento, no pude completar tu consulta en este momento."
    assert len(fake.calls) == llm.MAX_ITERATIONS


def _empty_msg():
    return {
        "output": {"message": {"role": "assistant", "content": []}},
        "stopReason": "content_filtered",
        "usage": {"inputTokens": 3, "outputTokens": 0},
    }


async def test_empty_reply_returns_fallback(monkeypatch):
    _passthrough_pii(monkeypatch)
    fake = _FakeClient([_empty_msg()])
    monkeypatch.setattr(llm, "client", lambda: fake)

    reply = await llm.chat("hola", customer_id="CUST-001", given_name="Juan")

    assert reply == "Lo siento, no pude procesar tu consulta en este momento."


async def test_multiple_tool_uses_in_one_turn(monkeypatch):
    _passthrough_pii(monkeypatch)

    async def fake_get_accounts(customer_id):
        return {"accounts": []}

    async def fake_list_products():
        return {"products": []}

    monkeypatch.setattr(llm, "get_accounts", fake_get_accounts)
    monkeypatch.setattr(llm, "list_products", fake_list_products)

    multi = {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"toolUse": {"toolUseId": "tu_a", "name": "get_my_accounts", "input": {}}},
                    {
                        "toolUse": {
                            "toolUseId": "tu_b",
                            "name": "get_product_info",
                            "input": {"product_type": "savings"},
                        }
                    },
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 15, "outputTokens": 6},
    }
    fake = _FakeClient([multi, _text_msg("Listo.")])
    monkeypatch.setattr(llm, "client", lambda: fake)

    reply = await llm.chat("dame cuentas y productos", customer_id="CUST-001", given_name="Juan")

    assert reply == "Listo."
    second = fake.calls[1]["messages"]
    results = [b for m in second for b in m["content"] if isinstance(b, dict) and "toolResult" in b]
    ids = {r["toolResult"]["toolUseId"] for r in results}
    assert ids == {"tu_a", "tu_b"}


async def test_faq_tool_round_trip(monkeypatch):
    _passthrough_pii(monkeypatch)

    async def fake_list_faq():
        return {
            "faq": [
                {
                    "topic": "certificates",
                    "title": "Certificados",
                    "content": "Solicitalo en la app o al *777.",
                }
            ]
        }

    monkeypatch.setattr(llm, "list_faq", fake_list_faq)

    fake = _FakeClient(
        [
            _tool_msg("tu_f", "get_faq", {"topic": "certificates"}),
            _text_msg("Puedes solicitar tu certificado en la app o al *777."),
        ]
    )
    monkeypatch.setattr(llm, "client", lambda: fake)

    reply = await llm.chat(
        "¿cómo solicito un certificado?", customer_id="CUST-001", given_name="Juan"
    )

    assert "*777" in reply
    second = fake.calls[1]["messages"]
    results = [b for m in second for b in m["content"] if isinstance(b, dict) and "toolResult" in b]
    assert results and results[0]["toolResult"]["toolUseId"] == "tu_f"
