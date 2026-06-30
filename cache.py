"""Extraction cache.

Caches the result of an AI extraction (normalized data + AI confidence map) on
disk, keyed by a hash of the file content, the processor, and the prompt
version. Re-uploading the same document for the same processor reuses the cached
result and **skips the Gemini call** — saving time and API cost.

The key includes ``prompt_version`` so improving a processor's prompts naturally
invalidates stale cache entries. Cache files live under ``outputs/cache/`` which
is git-ignored.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parent / "outputs" / "cache"


def make_key(file_bytes: bytes, processor_key: str, prompt_version: str) -> str:
    """Return a stable cache key for (content, processor, prompt version)."""
    digest = hashlib.sha1(file_bytes).hexdigest()
    return f"{processor_key}_{prompt_version}_{digest}"


def load(key: str) -> dict[str, Any] | None:
    """Return the cached extraction payload for a key, or None on a miss."""
    path = _CACHE_DIR / f"{key}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        logger.info("Extraction cache hit for %s.", key)
        return payload
    except Exception:  # noqa: BLE001 - a corrupt cache entry is a miss
        logger.debug("Failed to read cache entry %s; treating as miss.", key, exc_info=True)
        return None


def store(key: str, data: dict[str, Any], ai_scores: dict[str, Any]) -> None:
    """Persist an extraction result under a key (best-effort)."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"data": data, "ai_scores": ai_scores}
        (_CACHE_DIR / f"{key}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Cached extraction result for %s.", key)
    except Exception:  # noqa: BLE001 - caching must never break extraction
        logger.debug("Failed to write cache entry %s.", key, exc_info=True)
