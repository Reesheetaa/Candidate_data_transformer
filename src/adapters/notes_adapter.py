"""Adapter for free-text recruiter notes.

Extracts salary expectation, availability, and any skills mentioned, using
regex/keyword rules only.
"""

from __future__ import annotations

import re

from src.adapters.base_adapter import BaseAdapter
from src.extractors.email_extractor import extract_emails
from src.extractors.phone_extractor import extract_phones
from src.extractors.skill_extractor import extract_skills
from src.models import PartialCandidate
from src.utils import collapse_whitespace, read_text_file

_SALARY_RE = re.compile(
    r"(?i)(?:expected\s+salary|salary\s+expectation|ctc)\D{0,10}"
    r"(\d+(?:\.\d+)?\s*(?:lpa|lakhs?|k|lakh per annum)?)"
)
_AVAILABILITY_RE = re.compile(
    r"(?i)available\s+(?:in|from|by)?\s*([A-Za-z]+\s*\d{0,4}|immediately|\d+\s*weeks?|\d+\s*days?)"
)


class NotesAdapter(BaseAdapter):
    source_name = "notes"

    def parse(self, path: str) -> list[PartialCandidate]:
        if not path:
            return []
        text = read_text_file(path)
        if not text.strip():
            return []

        salary_match = _SALARY_RE.search(text)
        availability_match = _AVAILABILITY_RE.search(text)

        candidate = PartialCandidate(
            source=self.source_name,
            emails=extract_emails(text),
            phones=extract_phones(text),
            skills=extract_skills(text),
            salary_expectation=salary_match.group(1).strip() if salary_match else None,
            availability=availability_match.group(1).strip() if availability_match else None,
            notes=collapse_whitespace(text),
        )
        # emails = candidate.emails
        # candidate.candidate_key = (emails[0] if emails else None)
        emails = extract_emails(text)

        name = None
        for line in text.splitlines():
            line = line.strip()
            if (
                line
                and "@" not in line
                and not any(ch.isdigit() for ch in line)
                and 1 < len(line.split()) <= 4
            ):
                name = line
                break

        candidate.candidate_key = (
            emails[0]
            if emails
            else name.lower() if name else None
        )
        return [candidate]
