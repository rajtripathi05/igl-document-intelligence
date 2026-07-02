"""Duplicate-document detection.

Before processing, a document is fingerprinted by the SHA-1 of its raw bytes
(the same content hash used by the extraction cache and ``doc_id``). A small
persisted index (``outputs/fingerprints.json``) records when each fingerprint was
first processed, by which processor and department, so the UI can warn the
reviewer — "Already Processed" — and let them Continue Anyway or Cancel rather
than silently reprocessing.

The index stores no document content — only a hash and lightweight metadata.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_INDEX_PATH = Path(__file__).resolve().parent / "outputs" / "fingerprints.json"


def fingerprint(file_bytes: bytes) -> str:
    """Return the stable content fingerprint (SHA-1 hex) for a document."""
    return hashlib.sha1(file_bytes).hexdigest()


def _load_index() -> dict[str, Any]:
    """Load the fingerprint index (empty dict on any error / absence)."""
    if not _INDEX_PATH.is_file():
        return {}
    try:
        data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - tolerate a partial/corrupt index
        logger.debug("Failed to read fingerprint index.", exc_info=True)
        return {}


def check(fp: str) -> dict[str, Any] | None:
    """Return the stored record for a fingerprint, or None if never processed.

    The record contains ``{date, processor, department, filename,
    document_type}`` describing the first time this exact document was processed.
    """
    return _load_index().get(fp)


def record(
    fp: str,
    *,
    processor: str,
    department: str,
    filename: str,
    document_type: str,
) -> None:
    """Record that a document (by fingerprint) has been processed (best-effort).

    The first-seen record is preserved; re-processing does not overwrite it, so
    the "Already Processed" card always shows the original date/processor.
    """
    index = _load_index()
    if fp in index:
        return
    index[fp] = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "processor": processor,
        "department": department,
        "filename": filename,
        "document_type": document_type,
    }
    try:
        _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        _INDEX_PATH.write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001 - duplicate tracking must never break flow
        logger.debug("Failed to write fingerprint index.", exc_info=True)
