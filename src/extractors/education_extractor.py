"""Deterministic education extraction from resume-style text."""

from __future__ import annotations

import re

from src.constants import VALID_DEGREES
from src.models import Education

_DEGREE_RE = re.compile(
    r"(?i)\b(" + "|".join(re.escape(d) for d in VALID_DEGREES) + r")\b\.?"
)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# "<Degree> in <Field> ... <Institution> ... <Year>" style lines, handled heuristically
_IN_FIELD_RE = re.compile(r"(?i)\bin\s+([A-Za-z &]{3,40})")
_INSTITUTION_HINT_RE = re.compile(
    r"(?i)\b([A-Z][A-Za-z.& ]{2,60}\b(?:University|Institute|College|IIT|NIT|School))\b"
)


def _find_education_section(text: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"(?i)^\s*education\s*[:\-]?\s*$", line):
            block = []
            for nxt in lines[i + 1:]:
                if not nxt.strip():
                    break
                block.append(nxt)
            return "\n".join(block)
    return ""


def extract_education(text: str) -> list[Education]:
    """Best-effort extraction of education entries. Never raises on malformed text."""
    if not text:
        return []

    section = _find_education_section(text) or text
    entries: list[Education] = []

    for line in section.splitlines():
        line = line.strip()
        if not line:
            continue
        degree_match = _DEGREE_RE.search(line)
        if not degree_match:
            continue

        degree = degree_match.group(1)
        field_match = _IN_FIELD_RE.search(line)
        field = field_match.group(1).strip() if field_match else None

        inst_match = _INSTITUTION_HINT_RE.search(line)
        institution = inst_match.group(1).strip() if inst_match else None

        year_matches = re.findall(r"\b((?:19|20)\d{2})\b", line)
        end_year = int(year_matches[-1]) if year_matches else None

        entries.append(
            Education(
                institution=institution,
                degree=degree,
                field=field,
                end_year=end_year,
            )
        )

    return entries
