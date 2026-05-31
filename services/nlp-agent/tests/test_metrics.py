"""Unit tests for record_llm_usage with Anthropic-shaped usage objects."""

import types

from app import metrics


def test_record_llm_usage_reads_anthropic_token_fields():
    in_before = metrics.llm_tokens_total.labels(direction="input")._value.get()
    out_before = metrics.llm_tokens_total.labels(direction="output")._value.get()
    cost_before = metrics.llm_cost_usd_total._value.get()

    metrics.record_llm_usage(types.SimpleNamespace(input_tokens=100, output_tokens=50))

    assert metrics.llm_tokens_total.labels(direction="input")._value.get() - in_before == 100
    assert metrics.llm_tokens_total.labels(direction="output")._value.get() - out_before == 50
    assert metrics.llm_cost_usd_total._value.get() > cost_before


def test_record_llm_usage_ignores_none():
    cost_before = metrics.llm_cost_usd_total._value.get()
    metrics.record_llm_usage(None)
    assert metrics.llm_cost_usd_total._value.get() == cost_before
