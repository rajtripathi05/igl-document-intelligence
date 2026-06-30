"""Folder-backed, manifest-driven processor.

A :class:`FolderProcessor` turns a self-contained processor folder into a live
:class:`~processors.base.BaseProcessor` with **zero per-processor Python**:

    processors/<key>/
        manifest.json        # metadata, sections, line items, export mapping
        schema/schema.json   # explicit, hand-authored output schema
        prompts/<version>/   # system_prompt.txt + extraction_prompt.txt
        prompts/*.txt        # (flat fallback when no versioned folder exists)
        validator.py         # optional: validate(data) / auto_fix(data)
        exporter.py          # optional: build_excel_bytes(data)
        templates/, samples/ # business assets

Optional ``validator.py`` / ``exporter.py`` are loaded by file path via
``importlib.util`` (folders need not be importable packages). When absent, the
generic spec-driven validator/exporter are used. This is what lets the platform
scale to hundreds of processors: adding one is adding a folder.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Any

from config import ai_gateway
from gemini import GeminiClient
from processors import generic_exporter, generic_validator
from processors.base import BaseProcessor
from processors.spec import ProcessorSpec

logger = logging.getLogger(__name__)


class FolderProcessor(BaseProcessor):
    """A processor whose behaviour is fully defined by its folder + manifest."""

    def __init__(self, folder: Path, manifest: dict[str, Any]) -> None:
        """Initialize from a processor folder and its parsed manifest.

        Args:
            folder: The ``processors/<key>/`` directory.
            manifest: The parsed ``manifest.json`` contents.
        """
        self._folder = folder
        self._manifest = manifest
        self._spec = ProcessorSpec.from_manifest(manifest)
        self._module_cache: dict[str, ModuleType | None] = {}

    # ----- Identity ------------------------------------------------------- #

    @property
    def spec(self) -> ProcessorSpec:
        """Return the declarative specification built from the manifest."""
        return self._spec

    @property
    def folder(self) -> Path:
        """The processor's folder (used by the admin panel and exports)."""
        return self._folder

    # ----- Paths ---------------------------------------------------------- #

    def schema_path(self) -> Path:
        """Path to this processor's JSON schema."""
        return self._folder / "schema" / "schema.json"

    def _prompt_paths(self) -> tuple[Path, Path]:
        """Resolve (system_prompt, extraction_prompt) honouring prompt versioning.

        Prefers ``prompts/<prompt_version>/`` and falls back to flat
        ``prompts/*.txt`` for backward compatibility.
        """
        versioned = self._folder / "prompts" / self._spec.prompt_version
        base = versioned if versioned.is_dir() else self._folder / "prompts"
        return base / "system_prompt.txt", base / "extraction_prompt.txt"

    def template_path(self) -> Path | None:
        """Absolute path to the export template, or None when not declared."""
        export = self._spec.export
        if not export or not export.template:
            return None
        return self._folder / export.template

    # ----- AI client ------------------------------------------------------ #

    def build_client(self) -> GeminiClient:
        """Construct a Gemini client bound to this processor's prompts + schema."""
        system_prompt, extraction_prompt = self._prompt_paths()
        return GeminiClient(
            gateway=ai_gateway,
            system_prompt_path=system_prompt,
            extraction_prompt_path=extraction_prompt,
            schema_path=self.schema_path(),
        )

    # ----- Validation / auto-fix ------------------------------------------ #

    def validate(self, data: dict[str, Any]) -> list[str]:
        """Validate via the folder's ``validator.py`` or the generic validator."""
        module = self._optional_module("validator")
        if module and hasattr(module, "validate"):
            return list(module.validate(data))
        return generic_validator.validate(data, self._spec)

    def auto_fix(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Auto-fix via the folder's ``validator.py`` or the generic auto-fix."""
        module = self._optional_module("validator")
        if module and hasattr(module, "auto_fix"):
            fixed, notes = module.auto_fix(data)
            return fixed, list(notes)
        return generic_validator.auto_fix(data, self._spec)

    # ----- Excel ---------------------------------------------------------- #

    def build_excel_bytes(self, data: dict[str, Any]) -> bytes:
        """Build the per-document workbook via the folder's exporter or generic."""
        module = self._optional_module("exporter")
        if module and hasattr(module, "build_excel_bytes"):
            return module.build_excel_bytes(data)
        return generic_exporter.build_excel_bytes(data, self._spec)

    # ----- Optional module loading ---------------------------------------- #

    def _optional_module(self, name: str) -> ModuleType | None:
        """Import ``<folder>/<name>.py`` by file path, caching the result.

        Returns None when the module file is absent or is a placeholder (no
        callable ``validate``/``auto_fix``/``build_excel_bytes``). Import errors
        are logged and degrade gracefully to the generic implementations.
        """
        if name in self._module_cache:
            return self._module_cache[name]

        path = self._folder / f"{name}.py"
        module: ModuleType | None = None
        if path.is_file():
            try:
                spec = importlib.util.spec_from_file_location(
                    f"processors._loaded.{self._spec.use_case_key}.{name}", path
                )
                if spec and spec.loader:
                    candidate = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(candidate)
                    if any(
                        callable(getattr(candidate, attr, None))
                        for attr in ("validate", "auto_fix", "build_excel_bytes")
                    ):
                        module = candidate
            except Exception:  # noqa: BLE001 - never break discovery on a bad plugin
                logger.exception(
                    "Failed loading %s for processor '%s'; using generic.",
                    name,
                    self._spec.use_case_key,
                )

        self._module_cache[name] = module
        return module
