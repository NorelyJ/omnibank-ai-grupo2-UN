"""Redaction policy engine — pure function `apply_policy(text, entities, context)`.

Encodes the block / redact / pass-through rules:
  - CARD entities reject the whole request (BLOCK).
  - All other entity types are replaced with a `[TYPE]` placeholder (REDACT).
  - A PER entity equal to the authenticated user's first name passes through.
"""

from dataclasses import dataclass

from app.detector import Entity

_PLACEHOLDER = {
    "CEDULA": "[CÉDULA]",
    "NIT": "[NIT]",
    "PHONE": "[TELÉFONO]",
    "EMAIL": "[CORREO]",
    "ACCOUNT": "[CUENTA]",
    "IP": "[IP]",
    "PER": "[NOMBRE]",
    "LOC": "[UBICACIÓN]",
    "ORG": "[ORGANIZACIÓN]",
}

REDACT_WARNING = "Por tu seguridad, oculté algunos datos personales de tu mensaje."
BLOCK_WARNING = (
    "Por tu seguridad no puedo procesar números de tarjeta. "
    "Nunca compartas los datos de tu tarjeta por chat."
)


@dataclass(frozen=True)
class PolicyContext:
    """Per-request context. `given_name` is the authenticated user's first name."""

    given_name: str = ""


@dataclass(frozen=True)
class PolicyResult:
    text: str
    decision: str  # "REDACT" or "BLOCK"
    warning: str


def _is_authenticated_user_name(entity: Entity, context: PolicyContext) -> bool:
    """True for a PER entity equal to the authenticated user's first name."""
    if entity.type != "PER" or not context.given_name:
        return False
    return entity.original.strip().casefold() == context.given_name.strip().casefold()


def apply_policy(text: str, entities: list[Entity], context: PolicyContext) -> PolicyResult:
    # A card number anywhere rejects the whole request — block wins over redact.
    if any(e.type == "CARD" for e in entities):
        return PolicyResult(text="", decision="BLOCK", warning=BLOCK_WARNING)

    redacted = text
    placeholders_used = False
    for entity in sorted(entities, key=lambda e: e.start, reverse=True):
        if _is_authenticated_user_name(entity, context):
            continue
        placeholder = _PLACEHOLDER.get(entity.type)
        if placeholder is None:
            continue
        redacted = redacted[: entity.start] + placeholder + redacted[entity.end :]
        placeholders_used = True
    warning = REDACT_WARNING if placeholders_used else ""
    return PolicyResult(text=redacted, decision="REDACT", warning=warning)
