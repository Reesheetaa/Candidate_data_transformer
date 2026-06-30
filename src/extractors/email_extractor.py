"""Deterministic email extraction from free text."""

from __future__ import annotations

import re

from src.constants import EMAIL_REGEX


def extract_emails(text: str) -> list[str]:
    """Return all email-like substrings found in text, lowercased and deduped,
    preserving first-seen order."""
    if not text:
        return []
    found = re.findall(EMAIL_REGEX, text)
    seen: set[str] = set()
    result: list[str] = []
    for email in found:
        key = email.strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result
