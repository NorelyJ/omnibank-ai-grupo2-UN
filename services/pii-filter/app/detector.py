"""PII detector — pure function `detect(text) -> [Entity]`.

Hybrid: regex patterns for structured Colombian identifiers, spaCy NER for names,
locations and organizations. No I/O, no mutation of input.

When two patterns match overlapping spans (e.g. a NIT's 9-digit base also looks like
a cédula), the higher-priority entity wins and the overlapping one is dropped.
"""

import ipaddress
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Entity:
    type: str  # CEDULA, NIT, PHONE, EMAIL, ACCOUNT, CARD, IP, PER, LOC, ORG
    start: int
    end: int
    original: str


# Lower number = higher priority when spans overlap.
_PRIORITY = {
    "CARD": 0,
    "NIT": 1,
    "PHONE": 2,
    "IP": 3,
    "EMAIL": 4,
    "ACCOUNT": 5,
    "CEDULA": 6,
    "PER": 7,
    "LOC": 8,
    "ORG": 9,
}

# A run of digits, optionally grouped with dots — candidate cédula. The 8–10 digit
# count (Colombian cédula range) is enforced after stripping separators.
_DIGIT_RUN_RE = re.compile(r"\b\d[\d.]{6,12}\d\b")

# NIT: 9-digit base (optionally dot-grouped) + "-" + single check digit.
_NIT_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-\d\b")
_NIT_WEIGHTS = (3, 7, 13, 17, 19, 23, 29, 37, 41)

# Colombian mobile: 10 digits starting with 3, optional +57 country code, optional
# spaces/dots/dashes between groups.
_PHONE_RE = re.compile(r"(?:\+?57[\s.-]?)?\b3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}\b")

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# OmniBank internal account number: 3 uppercase letters + dash + 3–6 digits (e.g.
# AHO-001 savings, COR-204 checking, TDC-887 credit card).
_ACCOUNT_RE = re.compile(r"\b[A-Z]{3}-\d{3,6}\b")

# Card: 13–19 digits, optionally grouped with single spaces or dashes. The Luhn
# checksum is verified after stripping separators.
_CARD_RE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")


# IP candidates: a permissive shape, then validated by the stdlib `ipaddress` module.
_IPV4_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_IPV6_RE = re.compile(r"(?<![\w:])(?:[A-Fa-f0-9]{0,4}:){2,7}[A-Fa-f0-9]{0,4}(?![\w:])")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _nit_check_digit(base: str) -> int:
    """DIAN check-digit algorithm for a 9-digit NIT base."""
    total = sum(int(d) * w for d, w in zip(reversed(base), _NIT_WEIGHTS, strict=True))
    remainder = total % 11
    return remainder if remainder < 2 else 11 - remainder


def _detect_cedula(text: str) -> list[Entity]:
    out: list[Entity] = []
    for m in _DIGIT_RUN_RE.finditer(text):
        digits = m.group().replace(".", "")
        if 8 <= len(digits) <= 10:
            out.append(Entity("CEDULA", m.start(), m.end(), m.group()))
    return out


def _detect_nit(text: str) -> list[Entity]:
    out: list[Entity] = []
    for m in _NIT_RE.finditer(text):
        raw = m.group()
        base, check = raw.replace(".", "").split("-")
        if _nit_check_digit(base) == int(check):
            out.append(Entity("NIT", m.start(), m.end(), raw))
    return out


def _detect_phone(text: str) -> list[Entity]:
    return [Entity("PHONE", m.start(), m.end(), m.group()) for m in _PHONE_RE.finditer(text)]


def _detect_card(text: str) -> list[Entity]:
    out: list[Entity] = []
    for m in _CARD_RE.finditer(text):
        digits = re.sub(r"[ -]", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            out.append(Entity("CARD", m.start(), m.end(), m.group()))
    return out


def _detect_ip(text: str) -> list[Entity]:
    out: list[Entity] = []
    for regex, validator in ((_IPV4_RE, ipaddress.IPv4Address), (_IPV6_RE, ipaddress.IPv6Address)):
        for m in regex.finditer(text):
            try:
                validator(m.group())
            except ValueError:
                continue
            out.append(Entity("IP", m.start(), m.end(), m.group()))
    return out


def _detect_email(text: str) -> list[Entity]:
    return [Entity("EMAIL", m.start(), m.end(), m.group()) for m in _EMAIL_RE.finditer(text)]


def _detect_account(text: str) -> list[Entity]:
    return [Entity("ACCOUNT", m.start(), m.end(), m.group()) for m in _ACCOUNT_RE.finditer(text)]


# spaCy is loaded lazily on first use — the model is ~40MB and import is slow, so
# regex-only callers never pay for it. If the model is unavailable the detector
# degrades gracefully to regex-only rather than failing.
_nlp = None
_spacy_unavailable = False
_SPACY_LABELS = ("PER", "LOC", "ORG")


def _detect_spacy(text: str) -> list[Entity]:
    global _nlp, _spacy_unavailable
    if _spacy_unavailable:
        return []
    if _nlp is None:
        try:
            import spacy

            _nlp = spacy.load("es_core_news_md")
        except Exception:
            _spacy_unavailable = True
            return []
    return [
        Entity(ent.label_, ent.start_char, ent.end_char, ent.text)
        for ent in _nlp(text).ents
        if ent.label_ in _SPACY_LABELS
    ]


def _resolve_overlaps(candidates: list[Entity]) -> list[Entity]:
    """Greedily keep the highest-priority entity in any overlapping group."""
    accepted: list[Entity] = []
    for cand in sorted(candidates, key=lambda e: (_PRIORITY.get(e.type, 99), e.start)):
        if any(cand.start < a.end and a.start < cand.end for a in accepted):
            continue
        accepted.append(cand)
    return sorted(accepted, key=lambda e: e.start)


def warmup() -> None:
    """Eagerly load the spaCy model so the first real request meets the latency budget."""
    _detect_spacy("")


def detect(text: str) -> list[Entity]:
    candidates: list[Entity] = []
    candidates += _detect_card(text)
    candidates += _detect_nit(text)
    candidates += _detect_phone(text)
    candidates += _detect_ip(text)
    candidates += _detect_email(text)
    candidates += _detect_account(text)
    candidates += _detect_cedula(text)
    candidates += _detect_spacy(text)
    return _resolve_overlaps(candidates)
