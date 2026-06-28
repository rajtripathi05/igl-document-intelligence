"""Validation utilities for standardized Purchase Order data.

Validation is performed in Python (never by Gemini). The schema in
``schemas/purchase_order_schema.json`` is the single source of truth for the
normalized structure. This module ensures extracted data conforms to that
structure by merging it onto the schema skeleton and reporting issues.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _merge_onto_skeleton(skeleton: Any, data: Any) -> Any:
    """Recursively overlay ``data`` onto a copy of ``skeleton``.

    Keys present in the skeleton are filled from ``data`` when available,
    preserving the canonical structure. Lists (such as ``items``) are taken
    directly from the data when present.

    Args:
        skeleton: The schema-derived default structure.
        data: The extracted data to overlay.

    Returns:
        A structure matching the schema shape, populated from ``data``.
    """
    if isinstance(skeleton, dict):
        result: dict[str, Any] = {}
        source = data if isinstance(data, dict) else {}
        for key, default in skeleton.items():
            result[key] = _merge_onto_skeleton(default, source.get(key))
        # Preserve any extra keys the model provided (e.g. additional_information).
        for key, value in source.items():
            if key not in result:
                result[key] = value
        return result
    if isinstance(skeleton, list):
        return data if isinstance(data, list) else copy.deepcopy(skeleton)
    return data if data is not None else copy.deepcopy(skeleton)


def normalize_to_schema(
    data: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    """Normalize extracted data to the canonical schema shape.

    Args:
        data: Parsed extraction data from the model.
        schema: The canonical Purchase Order schema.

    Returns:
        Data conforming to the schema structure.
    """
    normalized = _merge_onto_skeleton(schema, data)
    logger.debug("Normalized extraction data to schema shape.")
    return normalized


def validate_purchase_order(data: dict[str, Any]) -> list[str]:
    """Validate a normalized Purchase Order and return a list of warnings.

    Checks performed:
    - Presence of mandatory top-level sections.
    - At least one line item.
    - Arithmetic consistency between line totals and the summary subtotal.

    Args:
        data: Normalized Purchase Order data.

    Returns:
        A list of human-readable validation messages (empty if all checks pass).
    """
    issues: list[str] = []

    required_sections = ["metadata", "buyer", "supplier", "purchase_order", "items", "summary"]
    for section in required_sections:
        if section not in data:
            issues.append(f"Missing required section: '{section}'.")

    po = data.get("purchase_order", {})
    if not po.get("po_number"):
        issues.append("Purchase Order number is missing.")

    items = data.get("items") or []
    if not items:
        issues.append("No line items were extracted.")

    # Cross-check the sum of taxable amounts against the reported subtotal.
    try:
        line_sum = sum(float(item.get("taxable_amount") or 0) for item in items)
        subtotal = float((data.get("summary") or {}).get("subtotal") or 0)
        if subtotal and abs(line_sum - subtotal) > 1.0:
            issues.append(
                f"Subtotal mismatch: line items sum to {line_sum:.2f} "
                f"but summary subtotal is {subtotal:.2f}."
            )
    except (TypeError, ValueError) as exc:
        issues.append(f"Could not verify numeric totals: {exc}")

    logger.info("Validation produced %d issue(s).", len(issues))
    return issues
