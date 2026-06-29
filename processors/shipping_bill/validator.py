"""Validation for the Shipping Bill processor.

Migrated verbatim from the V1.2 ``utils/shipping_bill_validators`` engine. The
schema is **unchanged**; only the prompt is improved. Validation runs in Python,
never by Gemini.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def validate(data: dict[str, Any]) -> list[str]:
    """Validate a normalized Shipping Bill and return a list of warnings.

    Checks performed:
    - Presence of mandatory top-level sections.
    - Presence of the Shipping Bill number.
    - Presence of the exporter IEC number.
    - At least one product line item.
    - FOB consistency: sum of line FOB values vs. summary total FOB value.
    - Weight consistency: net weight should not exceed gross weight.

    Args:
        data: Normalized Shipping Bill data.

    Returns:
        A list of human-readable validation messages (empty if all checks pass).
    """
    issues: list[str] = []

    required_sections = [
        "metadata",
        "shipping_bill",
        "exporter",
        "consignee",
        "invoice",
        "items",
        "summary",
    ]
    for section in required_sections:
        if section not in data:
            issues.append(f"Missing required section: '{section}'.")

    sb = data.get("shipping_bill", {}) or {}
    if not sb.get("shipping_bill_number"):
        issues.append("Shipping Bill number is missing.")

    exporter = data.get("exporter", {}) or {}
    if not exporter.get("iec_number"):
        issues.append("Exporter IEC number is missing.")

    items = data.get("items") or []
    if not items:
        issues.append("No product line items were extracted.")

    # FOB cross-check: sum of line FOB values vs reported total FOB value.
    try:
        line_fob = sum(float(item.get("fob_value") or 0) for item in items)
        total_fob = float((data.get("summary") or {}).get("total_fob_value") or 0)
        if total_fob and abs(line_fob - total_fob) > 1.0:
            issues.append(
                f"FOB mismatch: line items sum to {line_fob:.2f} "
                f"but summary total FOB value is {total_fob:.2f}."
            )
    except (TypeError, ValueError) as exc:
        issues.append(f"Could not verify FOB totals: {exc}")

    # Weight consistency: net weight must not exceed gross weight per line.
    for item in items:
        try:
            gross = float(item.get("gross_weight") or 0)
            net = float(item.get("net_weight") or 0)
            if gross and net and net > gross + 0.01:
                line = item.get("line_number") or "?"
                issues.append(
                    f"Line {line}: net weight ({net}) exceeds gross weight ({gross})."
                )
        except (TypeError, ValueError):
            continue

    logger.info("Shipping Bill validation produced %d issue(s).", len(issues))
    return issues
