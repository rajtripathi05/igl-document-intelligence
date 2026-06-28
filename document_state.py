"""Per-document state and the multi-document manager.

Each uploaded document carries its own original file, detected processor,
extracted/edited JSON, confidence map, and validation issues — independently.
The manager owns the collection and produces batch downloads (all JSON, all
Excel, and a combined ZIP).

This is document-type agnostic: the manager works with any processor through
the ``BaseProcessor`` interface.
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass, field
from typing import Any

from processors.base import BaseProcessor
from utils.file_handler import slugify
from utils.json_handler import to_json_bytes

logger = logging.getLogger(__name__)


@dataclass
class DocumentState:
    """All state for a single uploaded document.

    Attributes:
        doc_id: Stable identifier (unique within the session).
        filename: Original uploaded filename.
        file_bytes: Original document bytes.
        mime_type: Document MIME type.
        processor: The processor handling this document (None if unsupported).
        document_type: Detected document type label.
        classification_confidence: Confidence of the classification (0–100).
        classification_method: ``"ai"`` or ``"keyword"``.
        data: Standardized JSON (edited data becomes the source of truth).
        confidence: Flat ``{path: score}`` field confidence map.
        issues: Validation messages.
        status: Processing status label.
        error: Error message if processing failed.
    """

    doc_id: str
    filename: str
    file_bytes: bytes
    mime_type: str
    processor: BaseProcessor | None = None
    document_type: str = "Unknown"
    classification_confidence: int = 0
    classification_method: str = "ai"
    data: dict[str, Any] | None = None
    confidence: dict[str, int] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    status: str = "pending"
    error: str | None = None

    @property
    def supported(self) -> bool:
        """True if a processor was matched for this document."""
        return self.processor is not None

    @property
    def slug(self) -> str:
        """Filesystem-safe base name for outputs."""
        return slugify(self.filename)

    def json_filename(self) -> str:
        """Output filename for this document's JSON."""
        suffix = self.processor.spec.json_suffix if self.processor else "output"
        return f"{self.slug}_{suffix}.json"

    def excel_filename(self) -> str:
        """Output filename for this document's Excel workbook."""
        suffix = self.processor.spec.json_suffix if self.processor else "output"
        return f"{self.slug}_{suffix}.xlsx"

    def json_bytes(self) -> bytes:
        """Serialize this document's data to JSON bytes."""
        return to_json_bytes(self.data or {})

    def excel_bytes(self) -> bytes:
        """Generate this document's Excel workbook bytes."""
        if not self.processor or self.data is None:
            raise ValueError("Document has no processor or data for Excel export.")
        return self.processor.build_excel_bytes(self.data)


class DocumentManager:
    """Owns the collection of uploaded documents for the session."""

    def __init__(self) -> None:
        """Initialize an empty manager."""
        self._docs: dict[str, DocumentState] = {}

    @property
    def documents(self) -> list[DocumentState]:
        """All documents in insertion order."""
        return list(self._docs.values())

    def get(self, doc_id: str) -> DocumentState | None:
        """Return a document by id, or None."""
        return self._docs.get(doc_id)

    def add(self, doc: DocumentState) -> None:
        """Add or replace a document."""
        self._docs[doc.doc_id] = doc

    def remove(self, doc_id: str) -> None:
        """Remove a document by id."""
        self._docs.pop(doc_id, None)

    def clear(self) -> None:
        """Remove all documents."""
        self._docs.clear()

    def has(self, doc_id: str) -> bool:
        """True if a document with this id exists."""
        return doc_id in self._docs

    @property
    def processed(self) -> list[DocumentState]:
        """Documents that were successfully extracted."""
        return [d for d in self._docs.values() if d.supported and d.data is not None]

    # ----- Batch exports ------------------------------------------------- #

    def all_json_zip(self) -> bytes:
        """Return a ZIP archive of every processed document's JSON."""
        return self._zip(
            (d.json_filename(), d.json_bytes()) for d in self.processed
        )

    def all_excel_zip(self) -> bytes:
        """Return a ZIP archive of every processed document's Excel."""
        return self._zip(
            (d.excel_filename(), d.excel_bytes()) for d in self.processed
        )

    def full_zip(self) -> bytes:
        """Return a ZIP with both JSON and Excel for every processed document."""
        entries: list[tuple[str, bytes]] = []
        for d in self.processed:
            entries.append((d.json_filename(), d.json_bytes()))
            entries.append((d.excel_filename(), d.excel_bytes()))
        return self._zip(iter(entries))

    @staticmethod
    def _zip(entries: Any) -> bytes:
        """Build a ZIP archive from ``(name, bytes)`` entries."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in entries:
                archive.writestr(name, payload)
        return buffer.getvalue()
