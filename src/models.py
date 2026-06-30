"""Pydantic data models shared across the pipeline.

PartialCandidate is produced by adapters (one per source).
CanonicalCandidate is the single merged, internal representation.
Projection / validation operate on CanonicalCandidate without mutating it.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None  # ISO-3166 alpha-2


class Links(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None  # YYYY-MM
    end: Optional[str] = None  # YYYY-MM or "present"
    summary: Optional[str] = None


class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    end_year: Optional[int] = None


class SkillMention(BaseModel):
    """A raw skill mention before merging, tagged with its source."""

    name: str
    source: str


class SkillEntry(BaseModel):
    """A canonical skill in the merged candidate, with confidence and provenance."""

    name: str
    confidence: float
    sources: list[str] = Field(default_factory=list)


class ProvenanceEntry(BaseModel):
    field: str
    source: str
    method: str


class PartialCandidate(BaseModel):
    """Intermediate representation produced by a single adapter for a single source.

    Every adapter (csv / resume / notes) emits this same shape so the merge engine
    never needs to know where the data came from beyond the `source` tag.
    """

    source: str  # "csv" | "resume" | "notes"
    candidate_key: Optional[str] = None  # used to match rows/files to the same person

    full_name: Optional[str] = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Optional[Location] = None
    links: Optional[Links] = None
    headline: Optional[str] = None

    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)

    salary_expectation: Optional[str] = None
    availability: Optional[str] = None
    notes: Optional[str] = None

    raw_text: Optional[str] = None


class CanonicalCandidate(BaseModel):
    """The single, internal, source-of-truth representation of a candidate.

    Never mutated by the projection layer.
    """

    candidate_id: str
    full_name: Optional[str] = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: Optional[str] = None
    years_experience: Optional[float] = None

    skills: list[SkillEntry] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)

    salary_expectation: Optional[str] = None
    availability: Optional[str] = None

    provenance: list[ProvenanceEntry] = Field(default_factory=list)
    overall_confidence: float = 0.0


class ValidationResult(BaseModel):
    is_valid: bool
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
