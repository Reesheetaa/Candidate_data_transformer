"""Deterministic phone-number extraction from free text.

Extraction here is intentionally permissive (regex). Validation and E.164
normalization happen later in the normalizer, which uses the `phonenumbers`
library so that this module stays a pure best-effort candidate finder.
"""

from __future__ import annotations

import re

from src.constants import PHONE_REGEX


def extract_phones(text: str) -> list[str]:
    """Return raw phone-like substrings found in text, deduped, in first-seen order."""
    if not text:
        return []
    candidates = re.findall(PHONE_REGEX, text)
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        digits = re.sub(r"\D", "", raw)
        # Skip obvious non-phone numeric noise (too short / too long).
        if len(digits) < 8 or len(digits) > 15:
            continue
        if digits not in seen:
            seen.add(digits)
            cleaned.append(raw.strip())
    return cleaned
