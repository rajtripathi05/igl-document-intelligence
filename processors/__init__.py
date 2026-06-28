"""Document processor package.

Each document type (Purchase Order, Shipping Bill, ...) is implemented as a
self-contained processor that owns its own prompts, schema, validation, Excel
template, and SAP mapping. Processors share behaviour only through the
:class:`~processors.base.BaseProcessor` interface — never by reusing another
document type's concrete implementation.

A processor becomes available in the UI by registering itself against a
use-case key in :mod:`processors.registry`. Document types without a registered
processor render a "coming soon" placeholder.

To add a new document type (e.g. Shipping Bill) later, you only need to:

1. Add its prompts under ``prompts/``.
2. Add its JSON schema under ``schemas/``.
3. Add a processor module here implementing ``BaseProcessor``.
4. Register it in ``processors.registry`` against its use-case key.

No existing processor is modified.
"""

from __future__ import annotations

from processors.base import BaseProcessor
from processors.registry import get_processor, register_processor

__all__ = ["BaseProcessor", "get_processor", "register_processor"]
