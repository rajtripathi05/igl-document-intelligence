"""Validation for the Shipping Bill processor.

Migrated verbatim from the V1.2 ``utils/shipping_bill_validators`` engine. The
schema is **unchanged**; only the prompt is improved. Validation runs in Python,
never by Gemini.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from processors import generic_validator
from processors.spec import ProcessorSpec

logger = logging.getLogger(__name__)

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"


def _to_number(value: Any) -> float | None:
    """Best-effort numeric coercion (returns None when not parseable)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace(",", "").replace("%", "").strip()
        return float(cleaned) if cleaned else None
    except (TypeError, ValueError):
        return None


def _fob_value_inr(data: dict[str, Any]) -> float | None:
    """Return the FOB value expressed in INR, used as the DBK-rate divisor.

    The drawback amount is in INR while ``invoice.fob_value`` is the foreign-
    currency FOB, so FOB(INR) = FOB(FC) x customs exchange rate. Falls back to
    the summary total FOB, and to the raw FOB when no exchange rate is present
    (i.e. the stored FOB is already in INR).
    """
    invoice = data.get("invoice", {}) or {}
    summary = data.get("summary", {}) or {}
    rate = _to_number(invoice.get("exchange_rate"))
    for fob in (_to_number(invoice.get("fob_value")),
                _to_number(summary.get("total_fob_value"))):
        if fob and fob > 0:
            if rate and rate > 0:
                return fob * rate
            return fob
    return None


def auto_fix(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Deterministic auto-fix for Shipping Bills.

    Runs the shared spec-driven normalization first (date/number/whitespace),
    then derives the Drawback Rate (%) when it is missing but the DBK amount and
    a FOB value are available: ``DBK Rate = DBK Amount / FOB(INR) x 100``.
    """
    spec = ProcessorSpec.from_manifest(json.loads(_MANIFEST_PATH.read_text(encoding="utf-8")))
    data, notes = generic_validator.auto_fix(data, spec)

    drawback = data.get("drawback")
    if isinstance(drawback, dict) and drawback.get("dbk_rate") is None:
        dbk_amount = _to_number(drawback.get("dbk_amount"))
        fob_inr = _fob_value_inr(data)
        if dbk_amount and dbk_amount > 0 and fob_inr and fob_inr > 0:
            derived = round(dbk_amount / fob_inr * 100.0, 2)
            if 0 < derived < 100:  # sanity band for a plausible drawback rate
                drawback["dbk_rate"] = derived
                notes.append({
                    "field": "drawback.dbk_rate",
                    "old": None,
                    "new": derived,
                    "reason": (
                        "Derived DBK Rate = DBK Amount / FOB(INR) x 100 "
                        "(printed rate not found)."
                    ),
                    "confidence": 80,
                })

    return data, notes


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

    # Completeness review for customs/incentive fields. These are advisory
    # (not hard failures): they prompt the reviewer to confirm a value when it
    # is missing. A genuine zero (0 / 0.00) is a valid value and must NOT warn,
    # so we test for ``is None`` rather than falsiness.
    invoice = data.get("invoice", {}) or {}
    drawback = data.get("drawback", {}) or {}

    if invoice.get("commission") is None:
        issues.append("Commission is blank — confirm it is truly absent (0 is a valid value).")
    if not invoice.get("exchange_rate"):
        issues.append("Customs Exchange Rate is missing — please review.")

    if not any((item or {}).get("hs_code") for item in items):
        issues.append("HS Code is missing on every line item — please review.")

    if not sb.get("leo_date"):
        issues.append("LEO Date is missing — please review.")

    if drawback.get("dbk_rate") is None:
        issues.append("DBK Rate (%) is blank — please review.")
    if drawback.get("dbk_amount") is None:
        issues.append("DBK Amount is blank — confirm it is truly absent (0 is a valid value).")
    if drawback.get("rodtep_amount") is None:
        issues.append("RODTEP Amount is blank — confirm it is truly absent (0 is a valid value).")
    if not drawback.get("scheme_description"):
        issues.append("Scheme Description is missing — please review.")

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
