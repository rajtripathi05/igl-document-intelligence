"""Processing history.

Records every processed batch — when it ran, in which mode/department, how many
documents succeeded, and the generated per-type registers — so an operator can
review past runs and **download the registers again** without reprocessing.

Records live under ``outputs/history/<batch_id>/`` (git-ignored): a ``record.json``
plus the register ``.xlsx`` files generated at processing time.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import consolidated_excel

logger = logging.getLogger(__name__)

_HISTORY_DIR = Path(__file__).resolve().parent / "outputs" / "history"


def record_batch(docs: list, mode: str, department_name: str) -> dict[str, Any]:
    """Record a processed batch and persist its registers for re-download.

    Args:
        docs: The processed document states from the batch.
        mode: ``"Manual"`` or ``"Auto Detect"``.
        department_name: The department the batch was processed under.

    Returns:
        The persisted batch record dict.
    """
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    processed = [d for d in docs if getattr(d, "data", None) is not None and getattr(d, "processor", None)]

    by_type: dict[str, int] = {}
    for doc in processed:
        label = doc.processor.spec.business_process or doc.processor.spec.document_type
        by_type[label] = by_type.get(label, 0) + 1

    files: list[str] = []
    try:
        batch_dir = _HISTORY_DIR / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        for name, data in consolidated_excel.build_registers(processed).items():
            (batch_dir / name).write_bytes(data)
            files.append(name)
    except Exception:  # noqa: BLE001 - history must never break processing
        logger.exception("Failed to persist batch registers.")

    record = {
        "id": batch_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "department": department_name,
        "total": len(docs),
        "success": sum(1 for d in docs if getattr(d, "status", "") == "done"),
        "warnings": sum(1 for d in docs if getattr(d, "issues", None)),
        "errors": sum(1 for d in docs if getattr(d, "status", "") == "error"),
        "by_type": by_type,
        "files": files,
    }
    try:
        (_HISTORY_DIR / batch_id / "record.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to persist batch record.")
    logger.info("Recorded batch %s (%d docs).", batch_id, len(docs))
    return record


def list_batches() -> list[dict[str, Any]]:
    """Return all recorded batches, newest first."""
    if not _HISTORY_DIR.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for record_path in _HISTORY_DIR.glob("*/record.json"):
        try:
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001 - skip a corrupt record
            logger.debug("Skipping unreadable history record %s.", record_path, exc_info=True)
    records.sort(key=lambda r: r.get("id", ""), reverse=True)
    return records


def load_file(batch_id: str, filename: str) -> bytes | None:
    """Return the bytes of a stored register file for a batch, or None."""
    path = _HISTORY_DIR / batch_id / filename
    # Guard against path traversal: the resolved path must stay within the batch dir.
    try:
        base = (_HISTORY_DIR / batch_id).resolve()
        if not str(path.resolve()).startswith(str(base)):
            return None
        return path.read_bytes() if path.is_file() else None
    except Exception:  # noqa: BLE001
        return None
