"""Filesystem-based processor discovery.

Scans ``processors/*/manifest.json`` and registers a
:class:`~processors.folder_processor.FolderProcessor` for each. This is the
single mechanism that activates document types — there is **no hardcoded
import list and no per-processor registration code**. Adding a new processor is
purely adding a folder with a ``manifest.json``; it is picked up on the next
discovery pass (or immediately after the admin panel writes it and reruns).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from processors.folder_processor import FolderProcessor
from processors.registry import clear_registry, register_processor

logger = logging.getLogger(__name__)

_PROCESSORS_DIR = Path(__file__).resolve().parent


def discover_processors() -> list[FolderProcessor]:
    """Discover every valid folder processor under ``processors/``.

    Returns:
        Folder processors, ordered by department order then business process,
        so navigation is stable and grouped sensibly.
    """
    found: list[FolderProcessor] = []
    for manifest_path in sorted(_PROCESSORS_DIR.glob("*/manifest.json")):
        folder = manifest_path.parent
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            processor = FolderProcessor(folder, manifest)
            found.append(processor)
        except Exception:  # noqa: BLE001 - one bad manifest must not break the app
            logger.exception("Skipping invalid manifest at %s", manifest_path)

    found.sort(
        key=lambda p: (p.spec.department_order, p.spec.business_process.lower())
    )
    logger.info("Discovered %d processor(s).", len(found))
    return found


def discover_and_register(force: bool = False) -> int:
    """Discover and register all folder processors.

    Args:
        force: When True, clears the registry first (used by the admin panel to
            pick up a newly created or promoted processor without a restart).

    Returns:
        The number of processors registered.
    """
    if force:
        clear_registry()
    processors = discover_processors()
    for processor in processors:
        register_processor(processor)
    return len(processors)
