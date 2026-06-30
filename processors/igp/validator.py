"""Validation and deterministic auto-fix for the IGP (Inward Gate Pass) processor.

Business rules are derived from the uploaded TSMP register (the gate-pass
register that IGP rows feed into) and the IGP sample documents. Validation runs
in Python, never by Gemini. Auto-fix is deterministic (no AI): it normalizes
dates, coerces numeric quantities/values, and trims text, reporting each change
with a confidence score.
"""

from __future__ import annotations

import logging
from typing import Any

from processors.generic_validator import coerce_number, normalize_date

logger = logging.getLogger(__name__)

#: Date fields (dotted paths) normalized to ISO during auto-fix.
_DATE_PATHS = (
    ("purchase_order", "po_date"),
    ("delivery", "document_date"),
    ("gate_pass", "entry_date"),
    ("gate_pass", "manual_igp_date"),
    ("transporter", "gr_date"),
    ("permits", "mf4_date"),
)


def _note(field: str, old: Any, new: Any, reason: str, confidence: int) -> dict[str, Any]:
    """Build an auto-fix note record."""
    return {"field": field, "old": old, "new": new, "reason": reason, "confidence": confidence}


def auto_fix(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Normalize dates and numeric fields on a gate pass, reporting each change.

    Args:
        data: Normalized IGP data (mutated and returned).

    Returns:
        A ``(data, notes)`` tuple.
    """
    notes: list[dict[str, Any]] = []

    for section, key in _DATE_PATHS:
        block = data.get(section)
        if isinstance(block, dict) and block.get(key) not in (None, ""):
            old = block[key]
            new = normalize_date(old)
            if new and new != old:
                block[key] = new
                notes.append(_note(f"{section}.{key}", old, new, "Normalized date to ISO (YYYY-MM-DD).", 95))

    value = data.get("value")
    if isinstance(value, dict) and value.get("net_value_doc_currency") not in (None, ""):
        old = value["net_value_doc_currency"]
        new = coerce_number(old)
        if new is not None and new != old:
            value["net_value_doc_currency"] = new
            notes.append(_note("value.net_value_doc_currency", old, new, "Parsed numeric value.", 100))

    items = data.get("items")
    if isinstance(items, list):
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            if item.get("quantity") not in (None, ""):
                old = item["quantity"]
                new = coerce_number(old)
                if new is not None and new != old:
                    item["quantity"] = new
                    notes.append(_note(f"items[{index}].quantity", old, new, "Parsed numeric quantity.", 100))

    if notes:
        logger.info("IGP auto-fix applied %d change(s).", len(notes))
    return data, notes


def validate(data: dict[str, Any]) -> list[str]:
    """Validate a normalized Inward Gate Pass and return a list of warnings.

    Checks performed:
    - Presence of mandatory top-level sections.
    - At least one identifier (PO number or gate pass / material document number).
    - Vendor identification (code or name).
    - At least one material line item with a quantity.

    Args:
        data: Normalized IGP data.

    Returns:
        A list of human-readable validation messages (empty if all checks pass).
    """
    issues: list[str] = []

    required_sections = ["metadata", "gate_pass", "purchase_order", "vendor", "delivery", "items"]
    for section in required_sections:
        if section not in data:
            issues.append(f"Missing required section: '{section}'.")

    gate_pass = data.get("gate_pass", {}) or {}
    po = data.get("purchase_order", {}) or {}
    if not (
        po.get("po_number")
        or gate_pass.get("gate_pass_number")
        or gate_pass.get("material_document_number")
    ):
        issues.append("No PO number or gate pass / material document number was found.")

    vendor = data.get("vendor", {}) or {}
    if not (vendor.get("code") or vendor.get("name")):
        issues.append("Vendor is not identified (no vendor code or name).")

    items = data.get("items") or []
    real_items = [i for i in items if isinstance(i, dict) and any(v not in (None, "") for v in i.values())]
    if not real_items:
        issues.append("No material line items were extracted.")
    else:
        has_qty = any(
            (i.get("quantity") not in (None, "")) for i in real_items
        )
        if not has_qty:
            issues.append("No material quantity was extracted.")

    delivery = data.get("delivery", {}) or {}
    if not delivery.get("vehicle_number"):
        issues.append("Vehicle number is missing.")

    logger.info("IGP validation produced %d issue(s).", len(issues))
    return issues
