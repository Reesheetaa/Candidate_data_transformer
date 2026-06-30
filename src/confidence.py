"""Deterministic confidence scoring.

Base confidence comes from source reliability (constants.SOURCE_RELIABILITY).
Validity of the specific value adjusts it: a malformed phone/email gets a
heavy penalty rather than being dropped silently, so the consumer can decide
whether 0.40-confidence data is good enough.
"""

from __future__ import annotations

from src.constants import SOURCE_RELIABILITY

INVALID_VALUE_CONFIDENCE = 0.40
MULTI_SOURCE_BONUS = 0.05
MAX_CONFIDENCE = 0.99
VALIDATION_BONUS = 0.03
NORMALIZATION_BONUS = 0.02


def base_confidence(source: str) -> float:
    return SOURCE_RELIABILITY.get(source, 0.5)

def field_confidence(
    sources: list[str],
    is_valid: bool = True,
    normalized: bool = True,
    corroborated: bool = True,
) -> float:
    """
    Compute deterministic confidence for a merged field.

    Confidence depends on:
    - source reliability
    - validation status
    - successful normalization
    - agreement across multiple sources
    """

    if not sources:
        return 0.0

    # Invalid values receive a fixed low confidence
    if not is_valid:
        return INVALID_VALUE_CONFIDENCE

    score = max(base_confidence(s) for s in sources)

    # Same value found in multiple independent sources
    if corroborated and len(set(sources)) > 1:
        score += MULTI_SOURCE_BONUS

    # Successfully normalized (phone, email, date, skill alias, etc.)
    if normalized:
        score += NORMALIZATION_BONUS

    # Passed validation checks
    score += VALIDATION_BONUS

    return round(min(score, MAX_CONFIDENCE), 2)

# def field_confidence(sources: list[str], is_valid: bool = True) -> float:
#     """Confidence for a single merged field value.

#     - Starts from the highest reliability among contributing sources.
#     - Gets a small bonus if corroborated by more than one source.
#     - Gets clamped down hard if the value failed validation.
#     """
#     if not sources:
#         return 0.0
#     if not is_valid:
#         return INVALID_VALUE_CONFIDENCE

#     score = max(base_confidence(s) for s in sources)
#     if len(set(sources)) > 1:
#         score = min(MAX_CONFIDENCE, score + MULTI_SOURCE_BONUS)
#     return round(score, 2)


# def overall_confidence(field_scores: list[float]) -> float:
#     """Simple deterministic aggregate: mean of all populated field confidences."""
#     populated = [s for s in field_scores if s > 0]
#     if not populated:
#         return 0.0
#     return round(sum(populated) / len(populated), 2)

def overall_confidence(
    field_scores: list[float],
    expected_fields: int = 10,
) -> float:
    """
    Overall confidence balances two factors:

    1. Confidence of populated fields.
    2. Completeness of the candidate profile.

    A candidate with only a name and email should not receive the same
    confidence as a fully populated profile, even if those fields are
    individually very reliable.
    """

    populated = [s for s in field_scores if s > 0]

    if not populated:
        return 0.0

    average_confidence = sum(populated) / len(populated)

    completeness = min(len(populated) / expected_fields, 1.0)

    # 70% confidence quality
    # 30% profile completeness
    overall = (
        0.7 * average_confidence +
        0.3 * completeness
    )

    return round(overall, 2)

def explain_confidence(
    sources: list[str],
    is_valid: bool,
    normalized: bool,
    corroborated: bool,
) -> dict:
    """
    Returns an explanation of how the confidence score was computed.
    """

    explanation = {
        "base_source_confidence": max(base_confidence(s) for s in sources) if sources else 0.0,
        "multi_source_bonus": MULTI_SOURCE_BONUS if corroborated and len(set(sources)) > 1 else 0.0,
        "normalization_bonus": NORMALIZATION_BONUS if normalized else 0.0,
        "validation_bonus": VALIDATION_BONUS if is_valid else 0.0,
        "invalid_penalty": not is_valid,
    }

    explanation["final_confidence"] = field_confidence(
        sources=sources,
        is_valid=is_valid,
        normalized=normalized,
        corroborated=corroborated,
    )

    return explanation
