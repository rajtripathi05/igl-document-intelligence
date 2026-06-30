"""Shared schema-normalization utility.

Normalization is document-type agnostic: it merges extracted data onto a
processor's JSON-schema skeleton so the result always matches the canonical
structure. Each processor owns its own *validation* rules (in its folder's
``validator.py``); only this generic normalization is shared, and it is used by
the processing pipeline for every document type.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _merge_onto_skeleton(skeleton: Any, data: Any) -> Any:
    """Recursively overlay ``data`` onto a copy of ``skeleton``.

    Keys present in the skeleton are filled from ``data`` when available,
    preserving the canonical structure. Lists (such as ``items``) are taken
    directly from the data when present.

    Args:
        skeleton: The schema-derived default structure.
        data: The extracted data to overlay.

    Returns:
        A structure matching the schema shape, populated from ``data``.
    """
    if isinstance(skeleton, dict):
        result: dict[str, Any] = {}
        source = data if isinstance(data, dict) else {}
        for key, default in skeleton.items():
            result[key] = _merge_onto_skeleton(default, source.get(key))
        # Preserve any extra keys the model provided (e.g. additional_information).
        for key, value in source.items():
            if key not in result:
                result[key] = value
        return result
    if isinstance(skeleton, list):
        return data if isinstance(data, list) else copy.deepcopy(skeleton)
    return data if data is not None else copy.deepcopy(skeleton)


def normalize_to_schema(
    data: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    """Normalize extracted data to the canonical schema shape.

    Args:
        data: Parsed extraction data from the model.
        schema: The canonical Purchase Order schema.

    Returns:
        Data conforming to the schema structure.
    """
    normalized = _merge_onto_skeleton(schema, data)
    logger.debug("Normalized extraction data to schema shape.")
    return normalized
