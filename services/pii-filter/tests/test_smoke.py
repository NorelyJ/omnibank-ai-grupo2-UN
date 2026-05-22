from app.redactor import redact


def test_stub_redactor_is_passthrough():
    """Slice 1 stub returns input unchanged. Slice 2 replaces this with real PII detection."""
    text = "Mi cédula es 1020304050"
    out_text, decision, warning = redact(text=text, source="user_input", given_name="Juan")
    assert out_text == text
    assert decision == "REDACT"
    assert warning == ""


def test_stub_redactor_handles_empty():
    out_text, decision, warning = redact(text="", source="user_input", given_name="")
    assert out_text == ""
    assert decision == "REDACT"
    assert warning == ""
