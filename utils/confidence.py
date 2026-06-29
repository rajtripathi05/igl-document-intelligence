"""Field-level confidence scoring.

Confidence is sourced with a hybrid strategy that works for ANY processor
without modifying its prompts or schema:

1. AI-reported scores: the Gemini client may return a parallel ``_confidence``
   map keyed by dotted field path (0–100). These are used when present.
2. Heuristic fallback: for any field the model did not score, a deterministic
   heuristic estimates confidence from the value's shape (empty/null → low,
   well-formed identifiers/dates/numbers → high).

The result is a flat ``{dotted_path: int}`` map the UI consumes to colour-code
each field. None of this depends on a specific document type.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Confidence bands (percent). V2.0: green 95–100, yellow 75–94, red < 75.
HIGH_MIN = 95
REVIEW_MIN = 75

#: Key under which a processor's extraction may carry an AI confidence map.
AI_CONFIDENCE_KEY = "_confidence"

_GST_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{2}[/-]\d{2}[/-]\d{2,4}$")
_HSN_RE = re.compile(r"^\d{4,8}$")


def band(score: int) -> str:
    """Return the confidence band name for a score.

    Args:
        score: Confidence percentage (0–100).

    Returns:
        ``"high"``, ``"review"``, or ``"verify"``.
    """
    if score >= HIGH_MIN:
        return "high"
    if score >= REVIEW_MIN:
        return "review"
    return "verify"


def _heuristic_score(value: Any) -> int:
    """Estimate confidence for a single value from its shape.

    Args:
        value: The extracted value.

    Returns:
        An estimated confidence percentage (0–100).
    """
    if value is None:
        return 0
    if isinstance(value, bool):
        return 99
    if isinstance(value, (int, float)):
        return 97 if value != 0 else 80
    text = str(value).strip()
    if not text:
        return 0
    upper = text.upper()
    if _GST_RE.match(upper) or _PAN_RE.match(upper):
        return 99
    if _DATE_RE.match(text):
        return 96
    if _HSN_RE.match(text):
        return 98
    if len(text) <= 2:
        return 78
    # Long free text (addresses, descriptions) is reliable but not certain.
    return 92


def _flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts/lists into ``{dotted_path: scalar}`` pairs."""
    flat: dict[str, Any] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            if key == AI_CONFIDENCE_KEY:
                continue
            path = f"{prefix}.{key}" if prefix else key
            flat.update(_flatten(value, path))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            flat.update(_flatten(value, f"{prefix}[{index}]"))
    else:
        flat[prefix] = data
    return flat


def compute_confidence(
    data: dict[str, Any], ai_scores: dict[str, Any] | None = None
) -> dict[str, int]:
    """Compute a flat confidence map for every scalar field in ``data``.

    Args:
        data: Normalized document data.
        ai_scores: Optional AI-reported ``{path: score}`` map.

    Returns:
        A ``{dotted_path: int}`` confidence map.
    """
    ai_scores = ai_scores or {}
    flat = _flatten(data)
    scores: dict[str, int] = {}
    for path, value in flat.items():
        if path in ai_scores:
            try:
                scores[path] = max(0, min(100, int(round(float(ai_scores[path])))))
                continue
            except (TypeError, ValueError):
                pass
        scores[path] = _heuristic_score(value)
    logger.debug("Computed confidence for %d field(s).", len(scores))
    return scores


def field_score(
    confidence: dict[str, int], path: str, default: int = 90
) -> int:
    """Look up a field's confidence, falling back to a default."""
    return confidence.get(path, default)


def summarize(confidence: dict[str, int]) -> dict[str, int]:
    """Return counts of fields in each confidence band."""
    counts = {"high": 0, "review": 0, "verify": 0}
    for score in confidence.values():
        counts[band(score)] += 1
    return counts


def overall_confidence(confidence: dict[str, int]) -> int:
    """Return the overall document confidence as the mean of field scores.

    Empty/None fields (score 0) are excluded so a sparsely-populated document is
    not unfairly penalised; when every field is empty the result is 0.

    Args:
        confidence: A ``{path: score}`` field-confidence map.

    Returns:
        The rounded mean field confidence (0–100).
    """
    scores = [s for s in confidence.values() if s > 0]
    if not scores:
        return 0
    return int(round(sum(scores) / len(scores)))
