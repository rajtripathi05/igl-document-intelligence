"""JSON handling utilities for standardized Purchase Order data.

Provides helpers to robustly parse model output into JSON, load the canonical
schema, serialize data for download, and persist JSON to the ``outputs/``
directory.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load the Purchase Order JSON schema from disk.

    Args:
        schema_path: Absolute path to the schema JSON file.

    Returns:
        The parsed schema as a dictionary.

    Raises:
        FileNotFoundError: If the schema file does not exist.
        json.JSONDecodeError: If the schema file contains invalid JSON.
    """
    logger.debug("Loading schema from %s", schema_path)
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_model_json(raw_text: str) -> dict[str, Any]:
    """Parse raw model output into a JSON object.

    The model is instructed to return only JSON, but defensive parsing strips
    markdown code fences and extracts the first balanced JSON object when extra
    text is present.

    Args:
        raw_text: Raw text returned by the Gemini model.

    Returns:
        The parsed JSON object as a dictionary.

    Raises:
        ValueError: If no valid JSON object can be parsed from the text.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Model returned empty output; no JSON to parse.")

    cleaned = raw_text.strip()

    # Strip markdown code fences such as ```json ... ```.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Direct JSON parse failed; attempting to extract object.")

    # Fall back to extracting the outermost JSON object.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Could not parse JSON from model output: {exc}") from exc

    raise ValueError("No JSON object found in model output.")


def to_json_bytes(data: dict[str, Any]) -> bytes:
    """Serialize a dictionary to pretty-printed UTF-8 JSON bytes.

    Args:
        data: The data to serialize.

    Returns:
        UTF-8 encoded JSON suitable for download.
    """
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def save_json(data: dict[str, Any], output_path: Path) -> Path:
    """Persist JSON data to the given path.

    Args:
        data: The data to write.
        output_path: Destination file path.

    Returns:
        The path the file was written to.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    logger.info("Saved JSON to %s", output_path)
    return output_path
