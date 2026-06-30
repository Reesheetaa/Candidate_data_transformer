"""Merge engine: combines PartialCandidate objects (one per source) belonging
to the same person into a single CanonicalCandidate.

Merge policy (see README for rationale):
  - Name:          longest non-empty string wins
  - Emails/Phones: union after normalization, deduplicated
  - Skills:        canonical union, confidence boosted by multi-source corroboration
  - Education:     concatenated
  - Experience:    concatenated, sorted by start date (unknown dates last)
  - Salary:        prefer recruiter notes if present, else any other source
  - Availability:  prefer recruiter notes if present, else any other source

Every selected value is recorded in `provenance` with its source and method.
"""

from __future__ import annotations

from src.confidence import field_confidence, overall_confidence
from src.models import (
    CanonicalCandidate,
    Education,
    Experience,
    Links,
    Location,
    PartialCandidate,
    ProvenanceEntry,
    SkillEntry,
)
from src.normalizer import normalize_date, normalize_email, normalize_phone, normalize_skill
from src.utils import slugify
from src.report import write_merge_report


def _pick_longest_name(partials: list[PartialCandidate]) -> tuple[str | None, str | None]:
    best_name, best_source = None, None
    for p in partials:
        if p.full_name and (best_name is None or len(p.full_name) > len(best_name)):
            best_name, best_source = p.full_name, p.source
    return best_name, best_source


def _merge_emails(partials: list[PartialCandidate]) -> tuple[list[str], list[str]]:
    seen: dict[str, str] = {}  # normalized -> source of first sighting
    for p in partials:
        for raw in p.emails:
            norm = normalize_email(raw)
            if norm and norm not in seen:
                seen[norm] = p.source
    return list(seen.keys()), list(seen.values())


def _merge_phones(partials: list[PartialCandidate]) -> tuple[list[str], list[str], int]:
    seen: dict[str, str] = {}
    invalid_count = 0
    for p in partials:
        for raw in p.phones:
            norm = normalize_phone(raw)
            if norm is None:
                invalid_count += 1
                continue
            if norm not in seen:
                seen[norm] = p.source
    return list(seen.keys()), list(seen.values()), invalid_count


def _merge_location(partials: list[PartialCandidate]) -> tuple[Location, str | None]:
    for p in partials:
        if p.location and any([p.location.city, p.location.region, p.location.country]):
            return p.location, p.source
    return Location(), None


def _merge_links(partials: list[PartialCandidate]) -> tuple[Links, str | None]:
    merged = Links()
    source = None
    other: list[str] = []
    for p in partials:
        if not p.links:
            continue
        if p.links.linkedin and not merged.linkedin:
            merged.linkedin = p.links.linkedin
            source = source or p.source
        if p.links.github and not merged.github:
            merged.github = p.links.github
            source = source or p.source
        if p.links.portfolio and not merged.portfolio:
            merged.portfolio = p.links.portfolio
            source = source or p.source
        other.extend(p.links.other)
    merged.other = list(dict.fromkeys(other))
    return merged, source


def _merge_headline(partials: list[PartialCandidate]) -> tuple[str | None, str | None]:
    for p in partials:
        if p.headline:
            return p.headline, p.source
    return None, None


def _merge_skills(partials: list[PartialCandidate]) -> list[SkillEntry]:
    by_canonical: dict[str, list[str]] = {}
    for p in partials:
        for raw_skill in p.skills:
            canonical = normalize_skill(raw_skill)
            by_canonical.setdefault(canonical, []).append(p.source)

    entries = [
        SkillEntry(name=name, confidence=field_confidence(sources), sources=sorted(set(sources)))
        for name, sources in by_canonical.items()
    ]
    entries.sort(key=lambda e: (-e.confidence, e.name))
    return entries


def _merge_education(partials: list[PartialCandidate]) -> list[Education]:
    result: list[Education] = []
    seen: set[tuple] = set()
    for p in partials:
        for edu in p.education:
            key = (edu.institution, edu.degree, edu.field, edu.end_year)
            if key not in seen:
                seen.add(key)
                result.append(edu)
    return result


def _merge_experience(partials: list[PartialCandidate]) -> list[Experience]:
    result: list[Experience] = []
    seen: set[tuple] = set()
    for p in partials:
        for exp in p.experience:
            normalized = Experience(
                company=exp.company,
                title=exp.title,
                start=normalize_date(exp.start),
                end=normalize_date(exp.end) if exp.end and exp.end.lower() != "present" else exp.end,
                summary=exp.summary,
            )
            key = (normalized.company, normalized.title, normalized.start)
            if key not in seen:
                seen.add(key)
                result.append(normalized)

    def sort_key(exp: Experience):
        # Unknown start dates sort last (deterministic, stable).
        return (exp.start is None, exp.start or "")

    result.sort(key=sort_key, reverse=True)
    return result


def _merge_salary_and_availability(
    partials: list[PartialCandidate],
) -> tuple[str | None, str | None, str | None, str | None]:
    salary, salary_source = None, None
    availability, availability_source = None, None

    # Prefer recruiter notes first, per spec.
    ordered = sorted(partials, key=lambda p: 0 if p.source == "notes" else 1)
    for p in ordered:
        if salary is None and p.salary_expectation:
            salary, salary_source = p.salary_expectation, p.source
        if availability is None and p.availability:
            availability, availability_source = p.availability, p.source
    return salary, salary_source, availability, availability_source


def merge_candidate(partials: list[PartialCandidate], candidate_index: int = 0) -> CanonicalCandidate:
    """Merge all PartialCandidate objects believed to belong to the same person
    into a single CanonicalCandidate, with full provenance and confidence."""

    provenance: list[ProvenanceEntry] = []
    field_scores: list[float] = []
    merge_report = {
        "candidate": {},
        "fields": []
    }

    full_name, name_source = _pick_longest_name(partials)
    if name_source:
        provenance.append(ProvenanceEntry(field="full_name", source=name_source, method="longest_string"))
        field_scores.append(field_confidence([name_source]))
        merge_report["fields"].append(
            {
                "field": "full_name",
                "candidates": [
                    {
                        "value": p.full_name,
                        "source": p.source,
                    }
                    for p in partials
                    if p.full_name
                ],
                "selected": full_name,
                "sources": [name_source],
                "confidence": field_scores[-1],
                "reason": "Selected longest complete name",
            }
        )

    emails, email_sources = _merge_emails(partials)
    for email, source in zip(emails, email_sources):
        provenance.append(ProvenanceEntry(field=f"emails[{email}]", source=source, method="normalize+union"))
    if emails:
        field_scores.append(field_confidence(email_sources))
        merge_report["fields"].append(
            {
                "field": "emails",
                "selected": emails,
                "sources": email_sources,
                "confidence": field_scores[-1],
                "reason": "Normalized and deduplicated",
            }
        )

    phones, phone_sources, invalid_phone_count = _merge_phones(partials)
    for phone, source in zip(phones, phone_sources):
        provenance.append(ProvenanceEntry(field=f"phones[{phone}]", source=source, method="e164_normalize+union"))
    if phones:
        field_scores.append(field_confidence(phone_sources, is_valid=invalid_phone_count == 0))
        merge_report["fields"].append(
            {
                "field": "phones",
                "selected": phones,
                "sources": phone_sources,
                "confidence": field_scores[-1],
                "reason": "Normalized to E.164 and deduplicated",
            }
        )

    location, location_source = _merge_location(partials)
    if location_source:
        provenance.append(ProvenanceEntry(field="location", source=location_source, method="first_present"))
        field_scores.append(field_confidence([location_source]))

    links, links_source = _merge_links(partials)
    if links_source:
        provenance.append(ProvenanceEntry(field="links", source=links_source, method="first_present_per_field"))

    headline, headline_source = _merge_headline(partials)
    if headline_source:
        provenance.append(ProvenanceEntry(field="headline", source=headline_source, method="first_present"))
        field_scores.append(field_confidence([headline_source]))

    skills = _merge_skills(partials)
    for skill in skills:
        provenance.append(
            ProvenanceEntry(field=f"skills[{skill.name}]", source="+".join(skill.sources), method="canonical_union")
        )
        field_scores.append(skill.confidence)
        merge_report["fields"].append(
            {
                "field": f"skill:{skill.name}",
                "selected": skill.name,
                "sources": skill.sources,
                "confidence": skill.confidence,
                "reason": "Merged after canonicalization",
            }
        )

    education = _merge_education(partials)
    if education:
        edu_sources = [p.source for p in partials if p.education]
        provenance.append(ProvenanceEntry(field="education", source="+".join(edu_sources), method="concatenate_dedupe"))
        field_scores.append(field_confidence(edu_sources))
        merge_report["fields"].append(
            {
                "field": "education",
                "selected": len(education),
                "sources": edu_sources,
                "confidence": field_scores[-1],
                "reason": "Concatenated and deduplicated",
            }
        )

    experience = _merge_experience(partials)
    if experience:
        exp_sources = [p.source for p in partials if p.experience]
        provenance.append(ProvenanceEntry(field="experience", source="+".join(exp_sources), method="concatenate_sort_dedupe"))
        field_scores.append(field_confidence(exp_sources))
        merge_report["fields"].append(
            {
                "field": "experience",
                "selected": len(experience),
                "sources": exp_sources,
                "confidence": field_scores[-1],
                "reason": "Merged and sorted by start date",
            }
        )

    salary, salary_source, availability, availability_source = _merge_salary_and_availability(partials)
    if salary_source:
        provenance.append(ProvenanceEntry(field="salary_expectation", source=salary_source, method="prefer_notes"))
        field_scores.append(field_confidence([salary_source]))
        merge_report["fields"].append(
            {
                "field": "salary_expectation",
                "selected": salary,
                "sources": [salary_source],
                "confidence": field_scores[-1],
                "reason": "Recruiter notes preferred",
            }
        )
    if availability_source:
        provenance.append(ProvenanceEntry(field="availability", source=availability_source, method="prefer_notes"))
        field_scores.append(field_confidence([availability_source]))
        merge_report["fields"].append(
            {
                "field": "availability",
                "selected": availability,
                "sources": [availability_source],
                "confidence": field_scores[-1],
                "reason": "Recruiter notes preferred",
            }
        )

    years_experience = _estimate_years_experience(experience)

    candidate_id_seed = (emails[0] if emails else None) or full_name or f"candidate-{candidate_index}"
    candidate_id = slugify(candidate_id_seed)
    
    # merge_report["candidate"] = {
    #     "candidate_id": candidate_id,
    #     "overall_confidence": overall_confidence(field_scores),
    # }
    
    merge_report["candidate"] = {
        "candidate_id": candidate_id,
        "overall_confidence": overall_confidence(
            field_scores,
            expected_fields=10,
        ),
    }

    write_merge_report(
        merge_report,
        f"output/{candidate_id}_merge_report.json",
    )

    return CanonicalCandidate(
        candidate_id=candidate_id,
        full_name=full_name,
        emails=emails,
        phones=phones,
        location=location,
        links=links,
        headline=headline,
        years_experience=years_experience,
        skills=skills,
        experience=experience,
        education=education,
        salary_expectation=salary,
        availability=availability,
        provenance=provenance,
        # overall_confidence=overall_confidence(field_scores),
        overall_confidence=overall_confidence(
            field_scores,
            expected_fields=10,
        ),
    )


def _estimate_years_experience(experience: list[Experience]) -> float | None:
    """Rough deterministic estimate: sum of each entry's span in years,
    treating 'present' as the current year. Entries with unparseable dates
    are skipped rather than guessed."""
    from datetime import date

    total_months = 0
    counted_any = False
    for exp in experience:
        if not exp.start:
            continue
        try:
            start_year, start_month = (int(x) for x in exp.start.split("-"))
        except (ValueError, AttributeError):
            continue
        if exp.end == "present" or not exp.end:
            end_year, end_month = date.today().year, date.today().month
        else:
            try:
                end_year, end_month = (int(x) for x in exp.end.split("-"))
            except (ValueError, AttributeError):
                continue
        months = (end_year - start_year) * 12 + (end_month - start_month)
        if months > 0:
            total_months += months
            counted_any = True

    if not counted_any:
        return None
    return round(total_months / 12, 1)
