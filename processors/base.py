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

    def auto_fix(self, data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Deterministically repair common extraction issues before validation.

        Runs **no** AI. Returns the (possibly modified) data and a list of fix
        notes, each ``{"field", "old", "new", "reason", "confidence"}``. The
        default makes no changes; processors override via their folder
        ``validator.py`` or rely on the generic auto-fix.

        Args:
            data: Normalized document data.

        Returns:
            A ``(data, notes)`` tuple.
        """
        return data, []

    @abstractmethod
    def build_excel_bytes(self, data: dict[str, Any]) -> bytes:
        """Render this document type's per-document Excel workbook to bytes."""
        raise NotImplementedError

    def build_row(self, data: dict[str, Any]) -> dict[str, Any]:
        """Build a single consolidated-register row from this document's data.

        Returns an ordered ``{header: value}`` mapping driven by the spec's
        :class:`~processors.spec.ExportSpec`. The default returns an empty row
        when no export mapping is declared.

        Args:
            data: Normalized document data.

        Returns:
            An ordered dict of ``{column header: cell value}``.
        """
        export = self.spec.export
        if not export:
            return {}
        from processors.spec import resolve_export_value

        return {
            column.header: resolve_export_value(
                data, column, self.spec.line_items_path
            )
            for column in export.columns
        }

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
