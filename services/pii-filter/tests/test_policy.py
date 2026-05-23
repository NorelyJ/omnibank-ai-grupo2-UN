"""Tests for the redaction policy engine.

Entities are constructed directly so each test exercises the policy logic in
isolation from the detector's regex/spaCy behavior.
"""

from app.detector import Entity, detect
from app.policy import PolicyContext, apply_policy


def _ent(entity_type: str, text: str, substring: str) -> Entity:
    start = text.index(substring)
    return Entity(entity_type, start, start + len(substring), substring)


def test_redacts_cedula_and_warns():
    text = "mi cédula es 1020304050"
    result = apply_policy(text, [_ent("CEDULA", text, "1020304050")], PolicyContext())
    assert "1020304050" not in result.text
    assert "[CÉDULA]" in result.text
    assert result.decision == "REDACT"
    assert result.warning != ""


def test_blocks_request_containing_a_card():
    text = "mi tarjeta es 4532015112830366"
    result = apply_policy(text, [_ent("CARD", text, "4532015112830366")], PolicyContext())
    assert result.decision == "BLOCK"
    assert result.warning != ""
    assert "4532015112830366" not in result.text


def test_authenticated_user_first_name_passes_through():
    text = "hola, soy Juan y necesito ayuda"
    result = apply_policy(text, [_ent("PER", text, "Juan")], PolicyContext(given_name="Juan"))
    assert "Juan" in result.text
    assert "[NOMBRE]" not in result.text
    assert result.warning == ""


def test_other_person_name_is_redacted():
    text = "el dinero es para María"
    result = apply_policy(text, [_ent("PER", text, "María")], PolicyContext(given_name="Juan"))
    assert "María" not in result.text
    assert "[NOMBRE]" in result.text


def test_block_wins_when_card_is_mixed_with_redactable_entities():
    text = "cédula 1020304050 y tarjeta 4532015112830366"
    entities = [_ent("CEDULA", text, "1020304050"), _ent("CARD", text, "4532015112830366")]
    result = apply_policy(text, entities, PolicyContext())
    assert result.decision == "BLOCK"


def test_redaction_is_idempotent():
    text = "mi cédula 1020304050 y correo juan@correo.com, soy Andrés Gómez"
    once = apply_policy(text, detect(text), PolicyContext())
    twice = apply_policy(once.text, detect(once.text), PolicyContext())
    assert twice.text == once.text
