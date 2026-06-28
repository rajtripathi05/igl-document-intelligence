"""Common processor interface (declarative).

A processor is now a thin, declarative plugin. It exposes:

- :attr:`spec` — a :class:`~processors.spec.ProcessorSpec` describing its fields,
  sections, line items, classification keywords, and AI description.
- :meth:`build_client` — constructs a Gemini client bound to its own prompts and
  schema.
- :meth:`schema_path` — path to its JSON schema (single source of truth).
- :meth:`validate` — its independent validation engine.
- :meth:`build_excel_bytes` — its independent Excel generator.

The generic engine (``engine.py``) consumes these to provide extraction,
field-level confidence, inline editing, re-export, preview, and multi-document
handling — uniformly for every processor. Concrete processors share only this
interface, never each other's logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from gemini import GeminiClient
from processors.spec import ProcessorSpec


class BaseProcessor(ABC):
    """Abstract base class for a single document-type processor."""

    @property
    @abstractmethod
    def spec(self) -> ProcessorSpec:
        """Return the declarative specification for this processor."""
        raise NotImplementedError

    @property
    def use_case_key(self) -> str:
        """Stable use-case key (derived from the spec)."""
        return self.spec.use_case_key

    @abstractmethod
    def schema_path(self) -> Path:
        """Return the path to this processor's JSON schema."""
        raise NotImplementedError

    @abstractmethod
    def build_client(self) -> GeminiClient:
        """Construct a Gemini client bound to this processor's prompts/schema."""
        raise NotImplementedError

    @abstractmethod
    def validate(self, data: dict[str, Any]) -> list[str]:
        """Validate normalized data and return a list of human-readable issues."""
        raise NotImplementedError

    @abstractmethod
    def build_excel_bytes(self, data: dict[str, Any]) -> bytes:
        """Render this document type's Excel workbook to bytes."""
        raise NotImplementedError

    def save_excel(self, data: dict[str, Any], output_path: Path) -> Path:
        """Persist the Excel workbook to disk. Default writes the bytes.

        Args:
            data: Standardized document data.
            output_path: Destination path inside ``outputs/``.

        Returns:
            The path written to.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(self.build_excel_bytes(data))
        return output_path
