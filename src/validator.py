"""Validation engine: checks the projected output (and config) and returns
warnings instead of crashing wherever possible.
"""

from __future__ import annotations

import re

from src.constants import EMAIL_REGEX
from src.models import CanonicalCandidate, ValidationResult
from src.utils import get_nested

_EMAIL_FULL_RE = re.compile(rf"^{EMAIL_REGEX}$")
_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def validate_config(config: dict, candidate: CanonicalCandidate) -> list[str]:
    """Check that every `from` path in the config actually resolves against
    the candidate. Returns a list of warning strings (never raises)."""
    warnings: list[str] = []
    candidate_dict = candidate.model_dump()
    for field_spec in config.get("fields", []):
        source_path = field_spec.get("from", field_spec.get("path"))
        if not source_path:
            warnings.append(f"Config field entry missing both 'path' and 'from': {field_spec}")
            continue
        value = get_nested(candidate_dict, source_path)
        if value is None:
            warnings.append(f"Config path '{source_path}' did not resolve to any value")
    return warnings


def validate_candidate(candidate: CanonicalCandidate) -> ValidationResult:
    """Validate a CanonicalCandidate's data quality. Collects warnings rather
    than failing the run, per spec — only structurally impossible states are
    treated as errors."""
    warnings: list[str] = []
    errors: list[str] = []

    if not candidate.full_name:
        warnings.append("Missing full_name")
    if not candidate.emails:
        warnings.append("No email addresses found for candidate")
    else:
        for email in candidate.emails:
            if not _EMAIL_FULL_RE.match(email):
                warnings.append(f"Email failed format validation: {email}")

    if not candidate.phones:
        warnings.append("No phone numbers found for candidate")
    else:
        for phone in candidate.phones:
            if not _E164_RE.match(phone):
                warnings.append(f"Phone is not valid E.164: {phone}")

    if not candidate.skills:
        warnings.append("No skills found for candidate")
    else:
        # seen_skills = set()
        seen_skills: set[str] = set()

        for skill in candidate.skills:

            if not skill.name.strip():
                warnings.append(
                    "Encountered empty skill entry"
                )
                continue

            key = skill.name.lower()

            if key in seen_skills:
                warnings.append(
                    f"Duplicate skill after canonicalization: {skill.name}"
                )

            seen_skills.add(key)
            
    for exp in candidate.experience:
        
        if not exp.company:
            warnings.append(
                "Experience entry missing company"
            )

        if not exp.title:
            warnings.append(
                "Experience entry missing title"
            )
            
    for edu in candidate.education:

        if not edu.institution:
            warnings.append(
                "Education entry missing institution"
            )

        if not edu.degree:
            warnings.append(
                "Education entry missing degree"
            )
      
            
    if candidate.salary_expectation and candidate.salary_expectation.strip():

        if not re.search(
            r"\d",
            candidate.salary_expectation,
        ):
            warnings.append(
                "Salary expectation does not contain a numeric value"
            )


    # seen_emails = set()
    seen_emails: set[str] = set()
    for email in candidate.emails:
        if email in seen_emails:
            warnings.append(f"Duplicate email after normalization: {email}")
        seen_emails.add(email)
        
    # seen_phones = set()
    seen_phones: set[str] = set()
    for phone in candidate.phones:
        if phone in seen_phones:
            warnings.append(
                f"Duplicate phone after normalization: {phone}"
            )
        seen_phones.add(phone)

    if not candidate.candidate_id:
        errors.append("candidate_id is empty — this should never happen")

    return ValidationResult(is_valid=len(errors) == 0, warnings=warnings, errors=errors)
