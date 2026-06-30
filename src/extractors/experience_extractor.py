"""Deterministic work-experience extraction from resume-style text.

Heuristic: looks for lines of the form
  "<Title> at <Company> (<Start> - <End>)"
  "<Company> | <Title> | <Start> - <End>"
or a dedicated "Experience" section where each entry spans a few lines:
  Title, Company
  Mon YYYY - Mon YYYY (or "present")
  Summary line(s)
"""

from __future__ import annotations

import re

from src.constants import MONTHS
from src.models import Experience

_DATE_RANGE_RE = re.compile(
    r"(?i)([A-Za-z]{3,9}\.?\s+\d{4}|\d{4})\s*[-–to]+\s*(present|current|[A-Za-z]{3,9}\.?\s+\d{4}|\d{4})"
)
_TITLE_AT_COMPANY_RE = re.compile(r"(?i)^\s*(.+?)\s+at\s+(.+?)\s*(?:\(|$)")
_PIPE_RE = re.compile(r"\s*[|;]\s*")


def _normalize_month_year(token: str) -> str | None:
    token = token.strip().lower()
    if token in ("present", "current"):
        return "present"
    match = re.match(r"([a-z]{3,9})\.?\s+(\d{4})", token)
    if match:
        month_name, year = match.groups()
        month_num = MONTHS.get(month_name[:3].lower()) or MONTHS.get(month_name)
        if month_num:
            return f"{year}-{month_num:02d}"
        return year
    match = re.match(r"^(\d{4})$", token)
    if match:
        return match.group(1)
    return None


def _find_experience_section(text: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"(?i)^\s*(experience|work experience|employment)\s*[:\-]?\s*$", line):
            block = []
            for nxt in lines[i + 1:]:
                if re.match(r"(?i)^\s*(education|skills|projects?)\s*[:\-]?\s*$", nxt):
                    break
                block.append(nxt)
            return "\n".join(block)
    return ""


def extract_experience(text: str) -> list[Experience]:
    """Best-effort extraction of work experience entries. Never raises."""
    if not text:
        return []

    section = _find_experience_section(text) or text
    entries: list[Experience] = []

    lines = [l for l in section.splitlines() if l.strip()]
    pending_title: str | None = None
    pending_company: str | None = None

    for line in lines:
        line = line.strip()

        date_match = _DATE_RANGE_RE.search(line)
        title_company_match = _TITLE_AT_COMPANY_RE.match(line)

        if title_company_match:
            pending_title = title_company_match.group(1).strip()
            pending_company = title_company_match.group(2).strip()
            # Date might be on the same line
            if date_match:
                start = _normalize_month_year(date_match.group(1))
                end = _normalize_month_year(date_match.group(2))
                entries.append(
                    Experience(
                        company=pending_company,
                        title=pending_title,
                        start=start,
                        end=end,
                    )
                )
                pending_title = pending_company = None
            continue

        if _PIPE_RE.search(line) and not date_match:
            parts = _PIPE_RE.split(line)
            if len(parts) >= 2:
                pending_company, pending_title = parts[0].strip(), parts[1].strip()
            continue

        if date_match:
            start = _normalize_month_year(date_match.group(1))
            end = _normalize_month_year(date_match.group(2))
            entries.append(
                Experience(
                    company=pending_company,
                    title=pending_title,
                    start=start,
                    end=end,
                )
            )
            pending_title = pending_company = None
            continue

        # Otherwise treat as a summary line for the most recent entry.
        if entries and len(line) > 10:
            prev = entries[-1]
            prev.summary = (prev.summary + " " + line).strip() if prev.summary else line

    return entries
