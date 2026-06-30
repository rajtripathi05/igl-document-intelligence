"""Processor registry mapping use-case keys to processor instances.

A document type is "active" in the UI only if a processor is registered here
for its use-case key. Registration is the single integration point: adding a
new document processor never requires editing routing code in ``app.py``.
"""

from __future__ import annotations

import logging

from processors.base import BaseProcessor

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, BaseProcessor] = {}


def register_processor(processor: BaseProcessor) -> BaseProcessor:
    """Register a processor instance against its use-case key.

    Args:
        processor: A concrete processor whose ``use_case_key`` is set.

    Returns:
        The registered processor (so this can be used as a decorator-style call).

    Raises:
        ValueError: If the processor has no ``use_case_key``.
    """
    if not processor.use_case_key:
        raise ValueError("Processor must define a non-empty 'use_case_key'.")
    _REGISTRY[processor.use_case_key] = processor
    logger.info("Registered processor for use case '%s'.", processor.use_case_key)
    return processor


def get_processor(use_case_key: str) -> BaseProcessor | None:
    """Return the registered processor for a use-case key, or None.

    Args:
        use_case_key: The use-case key to look up.

    Returns:
        The processor instance, or None when no processor is registered (the
        document type is not yet implemented).
    """
    return _REGISTRY.get(use_case_key)


def clear_registry() -> None:
    """Remove all registered processors (used before a fresh discovery pass)."""
    _REGISTRY.clear()
    logger.info("Processor registry cleared.")


def all_processors() -> list[BaseProcessor]:
    """Return every registered processor (registration order preserved)."""
    return list(_REGISTRY.values())


def active_processors() -> list[BaseProcessor]:
    """Return only production (business-visible) processors."""
    return [p for p in _REGISTRY.values() if p.spec.active]


def processors_for_department(department_key: str) -> list[BaseProcessor]:
    """Return registered processors belonging to a department.

    Args:
        department_key: The department to filter by.

    Returns:
        Processors whose spec declares this department.
    """
    return [
        p for p in _REGISTRY.values() if p.spec.department_key == department_key
    ]


def production_processors_for_department(department_key: str) -> list[BaseProcessor]:
    """Return production processors in a department (classification candidates)."""
    return [
        p
        for p in _REGISTRY.values()
        if p.spec.department_key == department_key and p.spec.active
    ]


def business_processes_for_department(department_key: str) -> list[BaseProcessor]:
    """Return all processors (any status) for a department, navigation-ordered.

    Used to render the Business Process picker, which lists production processes
    alongside "coming soon" placeholders.
    """
    procs = [p for p in _REGISTRY.values() if p.spec.department_key == department_key]
    procs.sort(key=lambda p: p.spec.business_process.lower())
    return procs
