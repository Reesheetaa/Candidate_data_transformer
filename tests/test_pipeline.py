"""Unit tests for normalizer, merger, projector, and validator.

Run with: PYTHONPATH=. pytest tests/ -v
"""

from __future__ import annotations

import pytest

from src.merger import merge_candidate
from src.models import CanonicalCandidate, Links, Location, PartialCandidate
from src.normalizer import normalize_date, normalize_email, normalize_phone, normalize_skill
from src.projector import project
from src.validator import validate_candidate, validate_config


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------

def test_normalize_phone_with_separators():
    assert normalize_phone("+91 98765-43210") == "+919876543210"


def test_normalize_phone_without_country_code_defaults_to_india():
    assert normalize_phone("9876543210") == "+919876543210"


def test_normalize_phone_invalid_returns_none():
    assert normalize_phone("123") is None
    assert normalize_phone("") is None


def test_normalize_email_lowercases_and_trims():
    assert normalize_email("  John@GMAIL.com ") == "john@gmail.com"


def test_normalize_skill_known_alias():
    assert normalize_skill("py") == "Python"
    assert normalize_skill("cpp") == "C++"
    assert normalize_skill("js") == "JavaScript"


def test_normalize_skill_unknown_passes_through():
    assert normalize_skill("Quantum Basket Weaving") == "Quantum Basket Weaving"


def test_normalize_date_month_year():
    assert normalize_date("Jan 2023") == "2023-01"


def test_normalize_date_present_passthrough():
    assert normalize_date("present") == "present"


def test_normalize_date_empty_returns_none():
    assert normalize_date(None) is None
    assert normalize_date("") is None


# ---------------------------------------------------------------------------
# Merger
# ---------------------------------------------------------------------------

def test_merge_picks_longest_name():
    partials = [
        PartialCandidate(source="csv", full_name="A. Sharma"),
        PartialCandidate(source="resume", full_name="Aditi Sharma"),
    ]
    result = merge_candidate(partials)
    assert result.full_name == "Aditi Sharma"


def test_merge_unions_and_dedupes_emails():
    partials = [
        PartialCandidate(source="csv", emails=["Aditi@Gmail.com"]),
        PartialCandidate(source="resume", emails=["aditi@gmail.com", "second@example.com"]),
    ]
    result = merge_candidate(partials)
    assert result.emails == ["aditi@gmail.com", "second@example.com"]


def test_merge_prefers_notes_for_salary_and_availability():
    partials = [
        PartialCandidate(source="resume", salary_expectation="20 LPA"),
        PartialCandidate(source="notes", salary_expectation="22 LPA", availability="August"),
    ]
    result = merge_candidate(partials)
    assert result.salary_expectation == "22 LPA"
    assert result.availability == "August"


def test_merge_skills_corroborated_across_sources_gets_bonus_confidence():
    partials = [
        PartialCandidate(source="resume", skills=["python"]),
        PartialCandidate(source="notes", skills=["python"]),
    ]
    result = merge_candidate(partials)
    python_skill = next(s for s in result.skills if s.name == "Python")
    assert set(python_skill.sources) == {"resume", "notes"}
    assert python_skill.confidence > 0.90  # base resume reliability + corroboration bonus


def test_merge_handles_empty_input_gracefully():
    result = merge_candidate([PartialCandidate(source="csv")])
    assert result.full_name is None
    assert result.emails == []
    assert result.overall_confidence == 0.0


def test_merge_invalid_phone_lowers_confidence():
    partials = [PartialCandidate(source="csv", phones=["123"])]
    result = merge_candidate(partials)
    # Invalid phone is dropped from the list (cannot be normalized)...
    assert result.phones == []


# ---------------------------------------------------------------------------
# Projector
# ---------------------------------------------------------------------------

def _sample_canonical() -> CanonicalCandidate:
    return CanonicalCandidate(
        candidate_id="aditi-sharma",
        full_name="Aditi Sharma",
        emails=["aditi.sharma@gmail.com"],
        phones=["+919876543210"],
        location=Location(city="Bengaluru", country="IN"),
        links=Links(github="https://github.com/aditi"),
        headline="Backend Engineer",
        years_experience=5.0,
        overall_confidence=0.9,
    )


def test_project_identity_field():
    candidate = _sample_canonical()
    config = {"fields": [{"path": "full_name", "type": "string"}]}
    result = project(candidate, config)
    assert result["full_name"] == "Aditi Sharma"


def test_project_renames_and_remaps_indexed_path():
    candidate = _sample_canonical()
    config = {"fields": [{"path": "primary_email", "from": "emails[0]", "type": "string"}]}
    result = project(candidate, config)
    assert result["primary_email"] == "aditi.sharma@gmail.com"


def test_project_missing_field_on_missing_null():
    candidate = _sample_canonical()
    config = {"fields": [{"path": "salary_expectation", "type": "string"}], "on_missing": "null"}
    result = project(candidate, config)
    assert result["salary_expectation"] is None


def test_project_missing_field_on_missing_omit():
    candidate = _sample_canonical()
    config = {"fields": [{"path": "salary_expectation", "type": "string"}], "on_missing": "omit"}
    result = project(candidate, config)
    assert "salary_expectation" not in result


def test_project_includes_confidence_when_requested():
    candidate = _sample_canonical()
    config = {"fields": [{"path": "full_name", "type": "string"}], "include_confidence": True}
    result = project(candidate, config)
    assert result["overall_confidence"] == 0.9


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_validate_candidate_flags_missing_email():
    candidate = CanonicalCandidate(candidate_id="x", full_name="No Email Person")
    result = validate_candidate(candidate)
    assert any("email" in w.lower() for w in result.warnings)
    assert result.is_valid  # warnings don't make a candidate invalid


def test_validate_candidate_flags_bad_email_format():
    candidate = CanonicalCandidate(candidate_id="x", full_name="Bad Email", emails=["not-an-email"])
    result = validate_candidate(candidate)
    assert any("format" in w.lower() for w in result.warnings)


def test_validate_config_flags_unresolvable_path():
    candidate = _sample_canonical()
    config = {"fields": [{"path": "nonexistent_field", "from": "nonexistent_field"}]}
    warnings = validate_config(config, candidate)
    assert len(warnings) == 1
    assert "nonexistent_field" in warnings[0]


def test_validate_config_resolves_real_path_without_warning():
    candidate = _sample_canonical()
    config = {"fields": [{"path": "full_name"}]}
    warnings = validate_config(config, candidate)
    assert warnings == []
