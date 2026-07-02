"""Cost & usage tracking and prediction for AI extraction.

Captures token usage reported by the active provider per request and estimates
the rupee cost using configurable per-1K-token rates. Records are appended to
``outputs/usage/usage_log.jsonl`` (git-ignored) so the dashboard can show totals,
per-processor / per-department / per-month / per-model breakdowns, averages, and
retry usage. It also predicts the expected cost of a document *before* processing.

Rates are environment-configurable (no hardcoded pricing in business logic):
    AI_INPUT_COST_PER_1K_INR    (falls back to GEMINI_INPUT_COST_PER_1K_INR, 0.03)
    AI_OUTPUT_COST_PER_1K_INR   (falls back to GEMINI_OUTPUT_COST_PER_1K_INR, 0.12)
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_USAGE_DIR = Path(__file__).resolve().parent / "outputs" / "usage"
_USAGE_LOG = _USAGE_DIR / "usage_log.jsonl"

#: Model roles recorded per request.
ROLE_DEFAULT = "default"
ROLE_RETRY = "retry"

#: Heuristic token estimates used by :func:`predict` (before any AI call).
_PREDICT_BASE_INPUT_TOKENS = 2000  # prompt + schema + guidance overhead
_PREDICT_INPUT_TOKENS_PER_PAGE = 1200  # a rendered page image / native page
_PREDICT_OUTPUT_TOKENS = 900  # typical structured JSON output


def _rate(ai_name: str, legacy_name: str, default: float) -> float:
    """Read a per-1K-token INR rate, preferring the AI_* var then GEMINI_*."""
    for name in (ai_name, legacy_name):
        raw = os.getenv(name)
        if raw is not None and str(raw).strip():
            try:
                return float(raw)
            except (TypeError, ValueError):
                continue
    return default


def input_rate() -> float:
    """INR per 1K input tokens."""
    return _rate("AI_INPUT_COST_PER_1K_INR", "GEMINI_INPUT_COST_PER_1K_INR", 0.03)


def output_rate() -> float:
    """INR per 1K output tokens."""
    return _rate("AI_OUTPUT_COST_PER_1K_INR", "GEMINI_OUTPUT_COST_PER_1K_INR", 0.12)


def estimate_inr(input_tokens: int, output_tokens: int) -> float:
    """Estimate the rupee cost of a request from its token counts."""
    return (input_tokens / 1000.0) * input_rate() + (output_tokens / 1000.0) * output_rate()


def predict(num_pages: int, model: str) -> dict[str, Any]:
    """Predict the expected tokens and INR cost of a document before processing.

    Uses a page-count heuristic (no AI call). Intended to set expectations in the
    UI, not to be exact.

    Args:
        num_pages: Number of pages/images that will be sent to the model.
        model: The model that will process the document (for display).

    Returns:
        ``{expected_input_tokens, expected_output_tokens, expected_tokens,
        est_cost_inr, model}``.
    """
    pages = max(1, int(num_pages or 1))
    expected_input = _PREDICT_BASE_INPUT_TOKENS + pages * _PREDICT_INPUT_TOKENS_PER_PAGE
    expected_output = _PREDICT_OUTPUT_TOKENS
    return {
        "expected_input_tokens": expected_input,
        "expected_output_tokens": expected_output,
        "expected_tokens": expected_input + expected_output,
        "est_cost_inr": round(estimate_inr(expected_input, expected_output), 4),
        "model": model,
    }


def record(
    processor_key: str,
    department_key: str,
    model: str,
    usage: dict[str, int],
    *,
    model_role: str = ROLE_DEFAULT,
    proc_ms: int = 0,
    is_retry: bool = False,
) -> dict[str, Any]:
    """Record one request's usage and return the persisted record.

    Args:
        processor_key: Processor that made the request.
        department_key: Department the processor belongs to.
        model: Concrete model id used.
        usage: ``{"input_tokens", "output_tokens", "total_tokens"}``.
        model_role: ``"default"`` or ``"retry"`` — which model slot served it.
        proc_ms: Wall-clock processing time in milliseconds.
        is_retry: True when this record is a user-triggered retry.

    Returns:
        The record dict (also appended to the usage log).
    """
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or (input_tokens + output_tokens))
    now = datetime.now(timezone.utc)
    record_obj = {
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "month": now.strftime("%Y-%m"),
        "processor": processor_key,
        "department": department_key,
        "model": model,
        "model_role": model_role,
        "is_retry": bool(is_retry),
        "proc_ms": int(proc_ms or 0),
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


def _bucket() -> dict[str, float]:
    """A fresh aggregation bucket."""
    return {"docs": 0, "tokens": 0, "cost_inr": 0.0, "proc_ms": 0}


def summary() -> dict[str, Any]:
    """Return aggregated usage/cost for the dashboard.

    Returns:
        A dict with:
        - ``totals``: docs, tokens, cost_inr, proc_ms, and averages
          (avg_cost_inr, avg_tokens, avg_proc_ms).
        - ``today``: docs, tokens, cost_inr for the current UTC date.
        - ``retry_count``: number of retry requests recorded.
        - ``by_processor`` / ``by_department`` / ``by_month`` / ``by_model``:
          per-key {docs, tokens, cost_inr, proc_ms} breakdowns.
    """
    records = _load_records()
    by_processor: dict[str, dict[str, float]] = defaultdict(_bucket)
    by_department: dict[str, dict[str, float]] = defaultdict(_bucket)
    by_month: dict[str, dict[str, float]] = defaultdict(_bucket)
    by_model: dict[str, dict[str, float]] = defaultdict(_bucket)
    totals = _bucket()
    today = _bucket()
    retry_count = 0
    today_str = date.today().strftime("%Y-%m-%d")
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for rec in records:
        tokens = int(rec.get("total_tokens", 0) or 0)
        cost = float(rec.get("cost_inr", 0.0) or 0.0)
        proc_ms = int(rec.get("proc_ms", 0) or 0)
        for bucket, key in (
            (by_processor, rec.get("processor", "?")),
            (by_department, rec.get("department", "?")),
            (by_month, rec.get("month", "?")),
            (by_model, rec.get("model", "?")),
        ):
            bucket[key]["docs"] += 1
            bucket[key]["tokens"] += tokens
            bucket[key]["cost_inr"] = round(bucket[key]["cost_inr"] + cost, 4)
            bucket[key]["proc_ms"] += proc_ms
        totals["docs"] += 1
        totals["tokens"] += tokens
        totals["cost_inr"] = round(totals["cost_inr"] + cost, 4)
        totals["proc_ms"] += proc_ms
        if rec.get("is_retry"):
            retry_count += 1
        rec_date = rec.get("date")
        if rec_date in (today_str, today_utc):
            today["docs"] += 1
            today["tokens"] += tokens
            today["cost_inr"] = round(today["cost_inr"] + cost, 4)
            today["proc_ms"] += proc_ms

    docs = int(totals["docs"]) or 1
    totals["avg_cost_inr"] = round(totals["cost_inr"] / docs, 4)
    totals["avg_tokens"] = int(totals["tokens"] / docs)
    totals["avg_proc_ms"] = int(totals["proc_ms"] / docs)

    return {
        "totals": totals,
        "today": today,
        "retry_count": retry_count,
        "by_processor": dict(by_processor),
        "by_department": dict(by_department),
        "by_month": dict(by_month),
        "by_model": dict(by_model),
    }
