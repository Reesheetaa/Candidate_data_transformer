"""Adapter for resume files (.pdf or .txt).

Reads raw text, then delegates to the shared extractors. All extraction is
deterministic regex/heuristics only — no ML, no LLMs.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.adapters.base_adapter import BaseAdapter
from src.extractors.education_extractor import extract_education
from src.extractors.email_extractor import extract_emails
from src.extractors.experience_extractor import extract_experience
from src.extractors.phone_extractor import extract_phones
from src.extractors.skill_extractor import extract_skills
from src.models import PartialCandidate
from src.utils import collapse_whitespace, read_text_file

logger = logging.getLogger(__name__)


def _read_pdf_text(path: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed; cannot read PDF %s", path)
        return ""
    try:
        text_chunks: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text_chunks.append(page.extract_text() or "")
        return "\n".join(text_chunks)
    except Exception as exc:  # pdfplumber can raise various low-level errors
        logger.warning("Could not parse PDF at %s: %s", path, exc)
        return ""


def _guess_name(text: str) -> str | None:
    """Heuristic: the first non-empty line that looks like a person's name
    (2-4 capitalized words, no digits/@/commas) is usually the resume header."""
    for line in text.splitlines()[:5]:
        line = line.strip()
        if not line or "@" in line or any(ch.isdigit() for ch in line):
            continue
        words = line.split()
        if 1 < len(words) <= 4 and all(w[0:1].isupper() for w in words if w):
            return line
    return None


class ResumeAdapter(BaseAdapter):
    source_name = "resume"

    def parse(self, path: str) -> list[PartialCandidate]:
        if not path:
            return []
        suffix = Path(path).suffix.lower()
        if suffix == ".pdf":
            text = _read_pdf_text(path)
        else:
            text = read_text_file(path)

        text = text or ""
        if not text.strip():
            return []

        candidate = PartialCandidate(
            source=self.source_name,
            full_name=_guess_name(text),
            emails=extract_emails(text),
            phones=extract_phones(text),
            skills=extract_skills(text),
            education=extract_education(text),
            experience=extract_experience(text),
            raw_text=collapse_whitespace(text)[:5000],
        )
        emails = candidate.emails
        candidate.candidate_key = (emails[0] if emails else candidate.full_name or "").strip().lower() or None
        return [candidate]
