"""Custom Prometheus metrics for nlp-agent.

Registered on the default registry, so they appear on the `/metrics` endpoint that
prometheus-fastapi-instrumentator exposes. No label carries a customer identifier
(privacy rule: Prometheus must never become a PII store).
"""

from prometheus_client import Counter, Histogram

chat_requests_total = Counter(
    "omnibank_chat_requests_total",
    "Chat turns handled by the agent",
)

llm_calls_total = Counter(
    "omnibank_llm_calls_total",
    "LLM (Bedrock) calls, by model and outcome",
    ["model", "status"],
)

llm_tokens_total = Counter(
    "omnibank_llm_tokens_total",
    "LLM tokens consumed, by direction (input/output)",
    ["direction"],
)

llm_cost_usd_total = Counter(
    "omnibank_llm_cost_usd_total",
    "Estimated cumulative LLM spend in USD",
)

tool_calls_total = Counter(
    "omnibank_tool_calls_total",
    "Function-calling tool invocations, by tool name and outcome",
    ["tool_name", "status"],
)

redis_history_size = Histogram(
    "omnibank_redis_history_size",
    "Conversation-history message count loaded per turn",
    buckets=[0, 2, 4, 6, 8, 10, 15, 20],
)

# Llama 4 Maverick on Bedrock list price (USD per token), us-east-1. Estimate only.
_COST_PER_INPUT_TOKEN = 0.24 / 1_000_000
_COST_PER_OUTPUT_TOKEN = 0.97 / 1_000_000


def record_llm_usage(usage) -> None:
    """Record token counts and the estimated USD cost from a Bedrock Converse `usage` dict."""
    if not usage:
        return
    input_tokens = usage.get("inputTokens", 0) or 0
    output_tokens = usage.get("outputTokens", 0) or 0
    llm_tokens_total.labels(direction="input").inc(input_tokens)
    llm_tokens_total.labels(direction="output").inc(output_tokens)
    llm_cost_usd_total.inc(
        input_tokens * _COST_PER_INPUT_TOKEN + output_tokens * _COST_PER_OUTPUT_TOKEN
    )
