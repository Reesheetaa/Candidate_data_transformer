"""Small, generic helpers shared across modules."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def read_text_file(path: str | Path) -> str:
    """Read a text file as UTF-8, tolerating odd encodings. Never raises on bad bytes."""
    p = Path(path)
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return ""


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unknown"


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result


def get_nested(obj: Any, path: str) -> Any:
    """Resolve a dotted/bracketed path like 'skills[].name' or 'emails[0]' against
    a dict-like / pydantic-model-like structure.

    Supports:
      - "field"            -> obj["field"] or obj.field
      - "field.sub"        -> nested attribute/key access
      - "field[0]"         -> index into a list
      - "field[].sub"      -> map sub over every item in a list (returns a list)
    Returns None if any segment cannot be resolved (never raises).
    """

    def _get(o: Any, key: str) -> Any:
        if o is None:
            return None
        if isinstance(o, dict):
            return o.get(key)
        return getattr(o, key, None)

    tokens = re.findall(r"[^.\[\]]+|\[\d*\]", path)
    current: Any = obj
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("["):
            inner = token[1:-1]
            if current is None:
                return None
            if inner == "":
                # map remaining path over each element
                remaining = ".".join(
                    t for t in tokens[i + 1:] if not t.startswith("[")
                )
                # Reconstruct remaining raw path (handles further brackets too)
                remaining_tokens = tokens[i + 1:]
                if not remaining_tokens:
                    return list(current) if isinstance(current, list) else None
                results = []
                for item in current if isinstance(current, list) else []:
                    val = _resolve_tokens(item, remaining_tokens)
                    results.append(val)
                return results
            else:
                idx = int(inner)
                if isinstance(current, list) and -len(current) <= idx < len(current):
                    current = current[idx]
                else:
                    return None
        else:
            current = _get(current, token)
        i += 1
    return current


def _resolve_tokens(obj: Any, tokens: list[str]) -> Any:
    def _get(o: Any, key: str) -> Any:
        if o is None:
            return None
        if isinstance(o, dict):
            return o.get(key)
        return getattr(o, key, None)

    current = obj
    for token in tokens:
        if token.startswith("["):
            inner = token[1:-1]
            if inner == "":
                continue
            idx = int(inner)
            if isinstance(current, list) and -len(current) <= idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            current = _get(current, token)
    return current
