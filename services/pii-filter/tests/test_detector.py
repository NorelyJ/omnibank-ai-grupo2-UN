"""Tests for the PII detector — the heart of the project.

Each test calls the public `detect(text)` and asserts on the entities found, never
on internal regex objects or spaCy state.
"""

from app.detector import detect


def _types(text: str) -> set[str]:
    return {e.type for e in detect(text)}


def test_detects_plain_cedula():
    entities = detect("mi cédula es 1020304050, ayúdame")
    cedulas = [e for e in entities if e.type == "CEDULA"]
    assert len(cedulas) == 1
    assert cedulas[0].original == "1020304050"


def test_detects_dot_separated_cedula():
    entities = detect("cédula 1.020.304.050")
    cedulas = [e for e in entities if e.type == "CEDULA"]
    assert len(cedulas) == 1
    assert cedulas[0].original == "1.020.304.050"


def test_ignores_digit_runs_outside_cedula_length():
    assert "CEDULA" not in _types("el code es 12345")
    assert "CEDULA" not in _types("referencia 123456789012")


def test_detects_nit_with_valid_check_digit():
    entities = detect("nuestro NIT es 900.123.456-8")
    nits = [e for e in entities if e.type == "NIT"]
    assert len(nits) == 1
    assert nits[0].original == "900.123.456-8"
    # The 9-digit base must NOT also surface as a separate CEDULA.
    assert "CEDULA" not in {e.type for e in entities}


def test_rejects_nit_with_invalid_check_digit():
    assert "NIT" not in _types("NIT 900.123.456-1")


def test_detects_colombian_mobile_variants():
    assert "PHONE" in _types("llámame al +57 300 123 4567")
    assert "PHONE" in _types("mi celular 3001234567")
    assert "PHONE" in _types("tel 57 300 1234567")


def test_ignores_landline_short_numbers():
    assert "PHONE" not in _types("la oficina es 6012345")


def test_detects_email():
    entities = detect("escríbeme a juan.perez+banco@gmail.com cuando puedas")
    emails = [e for e in entities if e.type == "EMAIL"]
    assert len(emails) == 1
    assert emails[0].original == "juan.perez+banco@gmail.com"


def test_detects_luhn_valid_card():
    assert "CARD" in _types("mi tarjeta es 4532015112830366")
    assert "CARD" in _types("tarjeta 4532 0151 1283 0366")


def test_rejects_luhn_invalid_card():
    assert "CARD" not in _types("ese número 4532015112830367 no sirve")


def test_detects_ipv4_and_ipv6():
    assert "IP" in _types("se conectó desde 192.168.1.100")
    assert "IP" in _types("la dirección 2001:0db8:85a3::8a2e:0370:7334")


def test_rejects_invalid_ipv4_octets():
    assert "IP" not in _types("la version 999.999.1.1 no existe")


def test_detects_account_number():
    entities = detect("el saldo de la cuenta AHO-001 está disponible")
    accounts = [e for e in entities if e.type == "ACCOUNT"]
    assert len(accounts) == 1
    assert accounts[0].original == "AHO-001"


def test_ignores_non_account_codes():
    assert "ACCOUNT" not in _types("el ticket es AB-12")


def test_detects_person_name_via_spacy():
    assert "PER" in _types("hablé con Andrés Restrepo sobre el préstamo")


def test_detects_location_via_spacy():
    assert "LOC" in _types("la sucursal queda en Medellín")


def test_detects_organization_name_via_spacy():
    # The Spanish model tags companies inconsistently as ORG or LOC; either way the
    # name must be caught so it never leaks to the LLM.
    assert _types("trabajo en Ecopetrol desde hace años") & {"PER", "LOC", "ORG"}


def test_detects_mixed_content():
    text = "Soy Andrés, cédula 1020304050, celular 3001234567, correo a@b.com"
    found = _types(text)
    assert {"PER", "CEDULA", "PHONE", "EMAIL"} <= found


def test_text_without_pii_yields_no_entities():
    assert detect("¿cuál es el horario de atención los sábados?") == []


def test_handles_text_over_10kb_without_timeout():
    import time

    big = "el horario de atención es de lunes a viernes. " * 400  # ~18 KB
    start = time.monotonic()
    detect(big)
    assert time.monotonic() - start < 5.0
