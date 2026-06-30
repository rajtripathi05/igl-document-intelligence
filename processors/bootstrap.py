"""Processor bootstrap.

In V2.0 there is **no hardcoded processor list**. Every document type is a
self-contained folder under ``processors/<key>/`` with a ``manifest.json`` and
is activated by filesystem discovery (see :mod:`processors.discovery`).

Adding a new processor requires only creating a new folder — no edits here, in
the registry, or in any routing code.
"""

from __future__ import annotations

from processors.discovery import discover_and_register

_BOOTSTRAPPED = False


def bootstrap_processors() -> None:
    """Discover and register every folder processor exactly once."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    discover_and_register()
    _BOOTSTRAPPED = True


def refresh_processors() -> int:
    """Force a fresh discovery pass (used after admin creates/promotes a processor).

    Returns:
        The number of processors registered.
    """
    global _BOOTSTRAPPED
    count = discover_and_register(force=True)
    _BOOTSTRAPPED = True
    return count
