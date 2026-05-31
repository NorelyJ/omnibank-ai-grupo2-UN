"""Agent-loop tests with a mocked AsyncAnthropicBedrock client.

Only the external boundaries (pii-filter, banking, history, the Bedrock client)
are mocked. These drive the Anthropic tool-use loop in llm._run_agent_loop.
"""

import types

from app import llm
from app.pii_client import RedactResult


def _text_block(text):
    return types.SimpleNamespace(type="text", text=text)


def _tool_use_block(block_id, name, payload):
    return types.SimpleNamespace(type="tool_use", id=block_id, name=name, input=payload)


def _usage(input_tokens, output_tokens):
    return types.SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)


def _response(content, stop_reason, usage):
    return types.SimpleNamespace(content=content, stop_reason=stop_reason, usage=usage)


class _FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses):
        self.messages = _FakeMessages(responses)


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
    fake = _FakeClient([_response([_text_block("Hola, Juan.")], "end_turn", _usage(10, 5))])
    monkeypatch.setattr(llm, "client", lambda: fake)

    reply = await llm.chat("hola", customer_id="CUST-001", given_name="Juan")

    assert reply == "Hola, Juan."
    # System prompt is passed as a top-level param, not a message.
    assert "system" in fake.messages.calls[0]
    assert fake.messages.calls[0]["messages"][-1] == {"role": "user", "content": "hola"}


async def test_tool_use_round_trip(monkeypatch):
    _passthrough_pii(monkeypatch)

    async def fake_get_accounts(customer_id):
        return {"accounts": [{"id": "AHO-001", "balance": 5432100}]}

    monkeypatch.setattr(llm, "get_accounts", fake_get_accounts)

    responses = [
        _response([_tool_use_block("tu_1", "get_my_accounts", {})], "tool_use", _usage(20, 8)),
        _response([_text_block("Tu saldo es 5,432,100 COP.")], "end_turn", _usage(30, 12)),
    ]
    fake = _FakeClient(responses)
    monkeypatch.setattr(llm, "client", lambda: fake)

    reply = await llm.chat("¿cuál es mi saldo?", customer_id="CUST-001", given_name="Juan")

    assert "5,432,100" in reply
    second_messages = fake.messages.calls[1]["messages"]

    # The assistant turn (with its tool_use block) must precede the tool_result.
    assistant_turns = [m for m in second_messages if m["role"] == "assistant"]
    assert assistant_turns, "assistant turn must be threaded into the second call"
    assert any(b["type"] == "tool_use" for b in assistant_turns[-1]["content"])

    # The tool_result must reference the originating tool_use_id (load-bearing for
    # the real Bedrock API, which 400s on a mismatch).
    tool_results = [
        b
        for m in second_messages
        if isinstance(m["content"], list)
        for b in m["content"]
        if isinstance(b, dict) and b.get("type") == "tool_result"
    ]
    assert tool_results, "tool_result must be carried back to the model"
    assert tool_results[0]["tool_use_id"] == "tu_1"


async def test_max_iterations_exhaustion_returns_fallback(monkeypatch):
    _passthrough_pii(monkeypatch)

    async def fake_get_accounts(customer_id):
        return {"accounts": []}

    monkeypatch.setattr(llm, "get_accounts", fake_get_accounts)

    # The model asks for a tool every turn; the loop must give up after
    # MAX_ITERATIONS calls and return the fallback message.
    always_tool = [
        _response([_tool_use_block(f"tu_{i}", "get_my_accounts", {})], "tool_use", _usage(5, 1))
        for i in range(llm.MAX_ITERATIONS)
    ]
    fake = _FakeClient(always_tool)
    monkeypatch.setattr(llm, "client", lambda: fake)

    reply = await llm.chat("dame todo", customer_id="CUST-001", given_name="Juan")

    assert reply == "Lo siento, no pude completar tu consulta en este momento."
    assert len(fake.messages.calls) == llm.MAX_ITERATIONS
