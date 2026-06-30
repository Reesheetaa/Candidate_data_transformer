"""Adapter for the structured recruiter CSV export.

Each row becomes one PartialCandidate. Missing/empty rows are skipped gracefully.
"""

from __future__ import annotations

import logging

import pandas as pd

from src.adapters.base_adapter import BaseAdapter
from src.models import Links, Location, PartialCandidate

logger = logging.getLogger(__name__)

# Maps accepted CSV column names (lowercased, stripped) to our internal fields.
_COLUMN_ALIASES = {
    "full name": "full_name",
    "name": "full_name",
    "email": "email",
    "email address": "email",
    "phone": "phone",
    "phone number": "phone",
    "current company": "current_company",
    "company": "current_company",
    "current title": "current_title",
    "title": "current_title",
    "city": "city",
    "region": "region",
    "state": "region",
    "country": "country",
    "linkedin": "linkedin",
    "github": "github",
}


class CsvAdapter(BaseAdapter):
    source_name = "csv"

    def parse(self, path: str) -> list[PartialCandidate]:
        if not path:
            return []
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
            logger.warning("Could not read CSV at %s: %s", path, exc)
            return []

        df.columns = [str(c).strip().lower() for c in df.columns]
        candidates: list[PartialCandidate] = []

        for _, row in df.iterrows():
            fields: dict[str, str] = {}
            for col, value in row.items():
                key = _COLUMN_ALIASES.get(col)
                if key and str(value).strip():
                    fields[key] = str(value).strip()

            # Skip fully empty rows.
            if not any(fields.values()):
                continue

            full_name = fields.get("full_name")
            email = fields.get("email")
            phone = fields.get("phone")
            headline_parts = [p for p in (fields.get("current_title"), fields.get("current_company")) if p]
            headline = " at ".join(headline_parts) if headline_parts else None

            candidate = PartialCandidate(
                source=self.source_name,
                candidate_key=(email or full_name or "").strip().lower() or None,
                full_name=full_name,
                emails=[email] if email else [],
                phones=[phone] if phone else [],
                location=Location(
                    city=fields.get("city"),
                    region=fields.get("region"),
                    country=fields.get("country"),
                ),
                links=Links(
                    linkedin=fields.get("linkedin"),
                    github=fields.get("github"),
                ),
                headline=headline,
            )
            candidates.append(candidate)

        return candidates
