"""Cost & usage tracking for AI extraction.

Captures token usage reported by Gemini per request and estimates the rupee
cost using configurable per-1K-token rates. Usage records are appended to
``outputs/usage/usage_log.jsonl`` (git-ignored) so monthly totals and
per-processor / per-department cost can be shown in the dashboard.

Rates are environment-configurable (no hardcoded pricing in business logic):
    GEMINI_INPUT_COST_PER_1K_INR   (default 0.03)
    GEMINI_OUTPUT_COST_PER_1K_INR  (default 0.12)
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_USAGE_DIR = Path(__file__).resolve().parent / "outputs" / "usage"
_USAGE_LOG = _USAGE_DIR / "usage_log.jsonl"


def _rate(name: str, default: float) -> float:
    """Read a per-1K-token INR rate from the environment with a default."""
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def estimate_inr(input_tokens: int, output_tokens: int) -> float:
    """Estimate the rupee cost of a request from its token counts."""
    in_rate = _rate("GEMINI_INPUT_COST_PER_1K_INR", 0.03)
    out_rate = _rate("GEMINI_OUTPUT_COST_PER_1K_INR", 0.12)
    return (input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate


def record(
    processor_key: str,
    department_key: str,
    model: str,
    usage: dict[str, int],
) -> dict[str, Any]:
    """Record one request's usage and return the persisted record.

    Args:
        processor_key: Processor that made the request.
        department_key: Department the processor belongs to.
        model: Model used.
        usage: ``{"input_tokens", "output_tokens", "total_tokens"}``.

    Returns:
        The record dict (also appended to the usage log).
    """
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or (input_tokens + output_tokens))
    record_obj = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "month": datetime.now(timezone.utc).strftime("%Y-%m"),
        "processor": processor_key,
        "department": department_key,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_inr": round(estimate_inr(input_tokens, output_tokens), 4),
    }
    try:
        _USAGE_DIR.mkdir(parents=True, exist_ok=True)
        with _USAGE_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record_obj) + "\n")
    except Exception:  # noqa: BLE001 - cost tracking must never break extraction
        logger.debug("Failed to append usage record.", exc_info=True)
    return record_obj


def _load_records() -> list[dict[str, Any]]:
    """Load all persisted usage records (empty when none)."""
    if not _USAGE_LOG.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        for line in _USAGE_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    except Exception:  # noqa: BLE001 - tolerate a partially written log
        logger.debug("Failed to read usage log fully.", exc_info=True)
    return records


def summary() -> dict[str, Any]:
    """Return aggregated usage/cost for the dashboard.

    Returns:
        A dict with totals and per-processor / per-department / per-month
        breakdowns (documents, tokens, INR cost).
    """
    records = _load_records()
    by_processor: dict[str, dict[str, float]] = defaultdict(lambda: {"docs": 0, "tokens": 0, "cost_inr": 0.0})
    by_department: dict[str, dict[str, float]] = defaultdict(lambda: {"docs": 0, "tokens": 0, "cost_inr": 0.0})
    by_month: dict[str, dict[str, float]] = defaultdict(lambda: {"docs": 0, "tokens": 0, "cost_inr": 0.0})
    totals = {"docs": 0, "tokens": 0, "cost_inr": 0.0}

    for rec in records:
        tokens = int(rec.get("total_tokens", 0) or 0)
        cost = float(rec.get("cost_inr", 0.0) or 0.0)
        for bucket, key in (
            (by_processor, rec.get("processor", "?")),
            (by_department, rec.get("department", "?")),
            (by_month, rec.get("month", "?")),
        ):
            bucket[key]["docs"] += 1
            bucket[key]["tokens"] += tokens
            bucket[key]["cost_inr"] = round(bucket[key]["cost_inr"] + cost, 4)
        totals["docs"] += 1
        totals["tokens"] += tokens
        totals["cost_inr"] = round(totals["cost_inr"] + cost, 4)

    return {
        "totals": totals,
        "by_processor": dict(by_processor),
        "by_department": dict(by_department),
        "by_month": dict(by_month),
    }
