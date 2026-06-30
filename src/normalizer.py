"""Normalization functions: phones to E.164, emails lowercased, skills to
canonical names, dates to YYYY-MM. Normalization never resolves conflicts
between sources — that is the merge engine's job.
"""

from __future__ import annotations

import logging

import phonenumbers

from src.constants import DEFAULT_PHONE_REGION, SKILL_CANONICAL_MAP

logger = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_phone(raw: str, default_region: str = DEFAULT_PHONE_REGION) -> str | None:
    """Normalize a raw phone string to E.164 (e.g. +919876543210).

    Returns None if the number cannot be parsed as a plausible phone number.
    """
    if not raw:
        return None
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_possible_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def normalize_skill(raw: str) -> str:
    """Map a raw skill token to its canonical name, falling back to the
    original token (trimmed) if it isn't in the dictionary."""
    key = raw.strip().lower()
    if key in SKILL_CANONICAL_MAP:
        return SKILL_CANONICAL_MAP[key]
    return raw.strip()


def normalize_date(raw: str | None) -> str | None:
    """Normalize a free-form date string ('Jan 2023', '2023', '2023-01-15')
    to YYYY-MM where possible. Returns the original token if unparseable,
    and None for empty input."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower() in ("present", "current"):
        return "present"
    try:
        from datetime import datetime

        from dateutil import parser as date_parser

        # Use a fixed default so that a year-only or month-only input doesn't
        # silently pick up today's month/day (keeps output deterministic).
        dt = date_parser.parse(raw, default=datetime(1900, 1, 1), fuzzy=True)
        return f"{dt.year:04d}-{dt.month:02d}"
    except (ValueError, OverflowError, TypeError):
        return raw
