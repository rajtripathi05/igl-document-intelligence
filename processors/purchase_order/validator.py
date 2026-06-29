"""Validation for the Sales Order (Purchase Order) processor.

Migrated verbatim from the V1.2 ``utils/validators.validate_purchase_order``
engine — the AI extraction, schema, and business rules are unchanged; only the
business label (Marketing → Sales Order) differs. Validation runs in Python,
never by Gemini. Schema normalization remains the shared
``utils.validators.normalize_to_schema`` used by the processing pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def validate(data: dict[str, Any]) -> list[str]:
    """Validate a normalized Purchase/Sales Order and return a list of warnings.

    Checks performed:
    - Presence of mandatory top-level sections.
    - Presence of the order number.
    - At least one line item.
    - Arithmetic consistency between line totals and the summary subtotal.

    Args:
        data: Normalized order data.

    Returns:
        A list of human-readable validation messages (empty if all checks pass).
    """
    issues: list[str] = []

    required_sections = [
        "metadata",
        "buyer",
        "supplier",
        "purchase_order",
        "items",
        "summary",
    ]
    for section in required_sections:
        if section not in data:
            issues.append(f"Missing required section: '{section}'.")

    po = data.get("purchase_order", {})
    if not po.get("po_number"):
        issues.append("Order number is missing.")

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

    logger.info("Sales Order validation produced %d issue(s).", len(issues))
    return issues
