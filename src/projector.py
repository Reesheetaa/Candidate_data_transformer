"""Projection engine: turns a CanonicalCandidate into a runtime-configurable
JSON shape, per a JSON config. Never mutates the CanonicalCandidate.

Config schema:
{
  "fields": [
    { "path": "<output key>", "from": "<canonical path>", "type": "...",
      "required": bool, "normalize": "E164"|"canonical"|null }
  ],
  "include_confidence": bool,
  "include_provenance": bool,
  "on_missing": "null" | "omit" | "error"
}

If a field entry omits "from", the output path is used as the canonical path
(identity mapping) — this keeps the default config terse.
"""

from __future__ import annotations

from typing import Any

from src.models import CanonicalCandidate
from src.normalizer import normalize_phone, normalize_skill
from src.utils import get_nested


class ProjectionError(Exception):
    pass


def _apply_field_normalization(value: Any, normalize: str | None) -> Any:
    if normalize is None or value is None:
        return value
    if normalize == "E164":
        if isinstance(value, list):
            return [normalize_phone(v) or v for v in value]
        return normalize_phone(value) or value
    if normalize == "canonical":
        if isinstance(value, list):
            return [normalize_skill(v) for v in value]
        return normalize_skill(value)
    return value


def _set_output(output: dict, dotted_path: str, value: Any) -> None:
    """Set a (possibly dotted) output path into a nested dict, creating
    intermediate dicts as needed. Bracket notation is not supported on output
    paths — only on canonical-side `from` paths."""
    parts = dotted_path.split(".")
    current = output
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def project(candidate: CanonicalCandidate, config: dict) -> dict:
    """Project a CanonicalCandidate into a dict shaped by `config`."""
    fields = config.get("fields", [])
    include_confidence = config.get("include_confidence", False)
    include_provenance = config.get("include_provenance", False)
    on_missing = config.get("on_missing", "null")
    if on_missing not in ("null", "omit", "error"):
        raise ProjectionError(f"Invalid on_missing value: {on_missing!r}")

    candidate_dict = candidate.model_dump()
    output: dict = {}

    for field_spec in fields:
        output_path = field_spec.get("path")
        if not output_path:
            continue
        source_path = field_spec.get("from", output_path)
        required = field_spec.get("required", False)
        normalize = field_spec.get("normalize")

        value = get_nested(candidate_dict, source_path)
        value = _apply_field_normalization(value, normalize)

        is_missing = value is None or value == [] or value == ""
        if is_missing:
            if required and on_missing == "error":
                raise ProjectionError(f"Required field '{output_path}' is missing")
            if on_missing == "omit":
                continue
            if on_missing == "error" and required:
                raise ProjectionError(f"Required field '{output_path}' is missing")
            value = None if on_missing == "null" else value

        _set_output(output, output_path, value)

    if include_confidence:
        output["overall_confidence"] = candidate.overall_confidence
    if include_provenance:
        output["provenance"] = [p.model_dump() for p in candidate.provenance]

    return output
