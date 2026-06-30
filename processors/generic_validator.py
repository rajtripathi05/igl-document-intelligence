"""Generic, spec-driven validation and deterministic auto-fix.

These functions provide sensible default behaviour for any processor that does
not ship its own ``validator.py``. They are driven entirely by a processor's
:class:`~processors.spec.ProcessorSpec` (its declared fields, kinds, and
line-item columns) — there is no document-type-specific logic here.

Auto-fix is **deterministic** (no AI). It normalizes dates, coerces numbers, and
trims text, reporting every change with a confidence score so reviewers can see
exactly what was corrected and why.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from processors.spec import (
    FieldKind,
    FieldSpec,
    ProcessorSpec,
    get_path,
    set_path,
)

logger = logging.getLogger(__name__)

#: Date input formats accepted by :func:`normalize_date`, tried in order.
#: Day-first is assumed for ambiguous numeric dates (Indian business convention).
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y/%m/%d",
)

_NUMERIC_CLEAN_RE = re.compile(r"[^0-9.\-]")


def normalize_date(value: Any) -> str | None:
    """Return an ISO ``YYYY-MM-DD`` string for a recognizable date, else None.

    Args:
        value: A date string (or anything coercible to one).

    Returns:
        The ISO date string, or None when the value is empty or unrecognized.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            # strptime matches month names (%b/%B) case-insensitively, so
            # "27-JUN-2026" parses against "%d-%b-%Y" without extra handling.
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def coerce_number(value: Any) -> float | None:
    """Coerce a possibly-formatted value (``"₹1,234.50"``) to a float, else None.

    Args:
        value: A number or numeric string with optional currency/grouping marks.

    Returns:
        The parsed float, or None when the value cannot be parsed.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    cleaned = _NUMERIC_CLEAN_RE.sub("", text)
    if cleaned in ("", "-", ".", "-."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _note(field: str, old: Any, new: Any, reason: str, confidence: int) -> dict[str, Any]:
    """Build a single auto-fix note record."""
    return {
        "field": field,
        "old": old,
        "new": new,
        "reason": reason,
        "confidence": confidence,
    }


def auto_fix(
    data: dict[str, Any], spec: ProcessorSpec
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply deterministic, spec-driven fixes to ``data`` in place.

    Normalizes ``DATE`` fields to ISO, coerces ``NUMBER`` fields to floats, and
    trims surrounding whitespace on text fields — for both scalar section fields
    and line-item columns.

    Args:
        data: Normalized document data (mutated and returned).
        spec: The processor specification driving which fields to touch.

    Returns:
        A ``(data, notes)`` tuple; ``notes`` describes every change made.
    """
    notes: list[dict[str, Any]] = []

    for section in spec.sections:
        for fspec in section.fields:
            _fix_scalar(data, fspec, notes)

    if spec.line_items_path:
        items = get_path(data, spec.line_items_path)
        if isinstance(items, list):
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                for column in spec.line_item_columns:
                    _fix_line_item_cell(item, column, index, spec.line_items_path, notes)

    if notes:
        logger.info("Auto-fix applied %d change(s) for %s.", len(notes), spec.use_case_key)
    return data, notes


def _fix_scalar(data: dict[str, Any], fspec: FieldSpec, notes: list[dict[str, Any]]) -> None:
    """Normalize one scalar field, appending a note when it changes."""
    old = get_path(data, fspec.path)
    if old is None:
        return
    new = _normalize_value(old, fspec.kind)
    if new != old and new is not None:
        set_path(data, fspec.path, new)
        notes.append(_note(fspec.label, old, new, _reason_for(fspec.kind), _confidence_for(fspec.kind)))


def _fix_line_item_cell(
    item: dict[str, Any],
    column: Any,
    index: int,
    line_items_path: str,
    notes: list[dict[str, Any]],
) -> None:
    """Normalize one line-item cell, appending a note when it changes."""
    if column.key not in item:
        return
    old = item.get(column.key)
    if old is None:
        return
    new = _normalize_value(old, column.kind)
    if new != old and new is not None:
        item[column.key] = new
        label = f"{line_items_path}[{index}].{column.label}"
        notes.append(_note(label, old, new, _reason_for(column.kind), _confidence_for(column.kind)))


def _normalize_value(value: Any, kind: FieldKind) -> Any:
    """Return the normalized form of ``value`` for the given field kind."""
    if kind == FieldKind.NUMBER:
        return coerce_number(value)
    if kind == FieldKind.DATE:
        return normalize_date(value)
    if kind in (FieldKind.TEXT, FieldKind.LONG_TEXT):
        if isinstance(value, str):
            stripped = value.strip()
            return stripped
    return value


def _reason_for(kind: FieldKind) -> str:
    """Human-readable reason text for an auto-fix of the given kind."""
    if kind == FieldKind.NUMBER:
        return "Parsed numeric value (removed currency/grouping symbols)."
    if kind == FieldKind.DATE:
        return "Normalized date to ISO format (YYYY-MM-DD)."
    return "Trimmed surrounding whitespace."


def _confidence_for(kind: FieldKind) -> int:
    """Confidence for a deterministic auto-fix of the given kind."""
    if kind == FieldKind.DATE:
        return 95
    return 100


def validate(data: dict[str, Any], spec: ProcessorSpec) -> list[str]:
    """Validate ``data`` against the processor spec and return issue messages.

    Checks: data is present; declared ``required`` fields are non-empty; and,
    when the spec declares line items, that at least one was extracted.

    Args:
        data: Normalized document data.
        spec: The processor specification.

    Returns:
        A list of human-readable validation messages (empty when all pass).
    """
    issues: list[str] = []

    if not isinstance(data, dict) or not data:
        return ["No data was extracted from the document."]

    for section in spec.sections:
        for fspec in section.fields:
            if fspec.required:
                value = get_path(data, fspec.path)
                if value in (None, "", []):
                    issues.append(f"Required field missing: {fspec.label}.")

    if spec.line_items_path:
        items = get_path(data, spec.line_items_path)
        if not items:
            issues.append("No line items were extracted.")

    logger.info("Generic validation produced %d issue(s).", len(issues))
    return issues
