"""Tests for `redact()` — the function the gRPC server exposes.

`redact` wires the detector and the policy engine together; these tests verify the
end-to-end behavior of that wiring through its public signature.
"""

from app.redactor import redact


def test_redacts_cedula_from_user_input():
    out_text, decision, warning = redact(
        text="mi cédula es 1020304050", source="user_input", given_name="Juan"
    )
    assert "1020304050" not in out_text
    assert decision == "REDACT"
    assert warning != ""


def test_blocks_card_numbers():
    out_text, decision, warning = redact(
        text="mi tarjeta 4532015112830366", source="user_input", given_name="Juan"
    )
    assert decision == "BLOCK"
    assert "4532015112830366" not in out_text
    assert warning != ""


def test_clean_text_passes_through_unchanged():
    out_text, decision, warning = redact(
        text="¿cuál es el horario de atención?", source="user_input", given_name="Juan"
    )
    assert out_text == "¿cuál es el horario de atención?"
    assert decision == "REDACT"
    assert warning == ""


def test_authenticated_user_name_is_kept():
    out_text, decision, _ = redact(text="hola, soy Juan", source="user_input", given_name="Juan")
    assert "Juan" in out_text
    assert decision == "REDACT"


def test_handles_empty_text():
    out_text, decision, warning = redact(text="", source="user_input", given_name="")
    assert out_text == ""
    assert decision == "REDACT"
    assert warning == ""
