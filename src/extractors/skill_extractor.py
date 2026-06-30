"""Deterministic skill extraction via dictionary + fuzzy matching.

Strategy:
  1. Look for an explicit "Skills" section (common in resumes) and split it on
     commas / bullets / pipes.
  2. Additionally scan the whole text for any known skill alias as a whole-word match.
  3. Fuzzy-match leftover comma-separated tokens against the canonical vocabulary
     (handles minor typos) using rapidfuzz, but only accepts high-confidence matches.

Canonicalization itself (alias -> canonical name) happens in the normalizer; this
module returns the *raw* tokens it found so provenance/normalization stay separate.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from src.constants import KNOWN_SKILLS, SKILL_CANONICAL_MAP

_SECTION_HEADER_RE = re.compile(
    r"(?im)^\s*(skills|technical skills|key skills)\s*[:\-]?\s*$"
)


def _extract_skills_section(text: str) -> str:
    """Return the text block following a 'Skills' header, up to the next blank-line
    section break or the next ALL-CAPS-looking header line."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if _SECTION_HEADER_RE.match(line) or re.match(
            r"(?i)^\s*(skills|technical skills|key skills)\s*[:\-]\s*\S", line
        ):
            # Header may include content on the same line after ':'
            same_line = re.split(r"(?i)skills\s*[:\-]\s*", line, maxsplit=1)
            block_lines = []
            if len(same_line) > 1 and same_line[1].strip():
                block_lines.append(same_line[1])
            for nxt in lines[i + 1:]:
                if not nxt.strip():
                    break
                if re.match(r"^[A-Z][A-Za-z ]{2,20}:?\s*$", nxt.strip()) and len(
                    nxt.split()
                ) <= 3 and nxt.strip().isupper():
                    break
                block_lines.append(nxt)
            return " ".join(block_lines)
    return ""


def _scan_known_aliases(text: str) -> list[str]:
    found = []
    lower = text.lower()
    # for alias in SKILL_CANONICAL_MAP:
    for alias in sorted(
        SKILL_CANONICAL_MAP,
        key=len,
        reverse=True,
    ):
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, lower):
            found.append(alias)
    return found


def extract_skills(text: str, fuzzy_threshold: int = 88) -> list[str]:
    """Return raw skill tokens (not yet canonicalized) found in `text`."""
    if not text:
        return []

    raw_tokens: list[str] = []

    section = _extract_skills_section(text)
    if section:
        tokens = re.split(r"[,/|•\u2022;]+", section)
        raw_tokens.extend(t.strip() for t in tokens if t.strip())

    raw_tokens.extend(_scan_known_aliases(text))

    # Fuzzy match any leftover tokens against the canonical vocabulary.
    # canonical_pool = list(KNOWN_SKILLS)
    canonical_pool = sorted(
        KNOWN_SKILLS,
        key=len,
        reverse=True,
    )
    final: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        key = token.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        if key in SKILL_CANONICAL_MAP:
            final.append(token.strip())
            continue
        match = process.extractOne(
            token, canonical_pool, scorer=fuzz.WRatio, score_cutoff=fuzzy_threshold
        )
        if match:
            final.append(token.strip())
        elif len(token.split()) <= 3:
            # Unknown but short/plausible skill phrase: keep as-is (per spec:
            # "Unknown skills are retained as-is if not found in the dictionary").
            final.append(token.strip())

    return final
