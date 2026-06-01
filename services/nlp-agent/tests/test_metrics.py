"""Unit tests for record_llm_usage with Bedrock Converse usage dicts."""

from app import metrics


def test_record_llm_usage_reads_converse_token_fields():
    in_before = metrics.llm_tokens_total.labels(direction="input")._value.get()
    out_before = metrics.llm_tokens_total.labels(direction="output")._value.get()
    cost_before = metrics.llm_cost_usd_total._value.get()

    metrics.record_llm_usage({"inputTokens": 100, "outputTokens": 50})

    assert metrics.llm_tokens_total.labels(direction="input")._value.get() - in_before == 100
    assert metrics.llm_tokens_total.labels(direction="output")._value.get() - out_before == 50
    assert metrics.llm_cost_usd_total._value.get() > cost_before


def test_record_llm_usage_ignores_none():
    cost_before = metrics.llm_cost_usd_total._value.get()
    metrics.record_llm_usage(None)
    assert metrics.llm_cost_usd_total._value.get() == cost_before
