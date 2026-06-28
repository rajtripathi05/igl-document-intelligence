"""Declarative processor specification model.

A processor describes *what* it extracts (sections, fields, line-item columns)
and *how to classify* it (keywords, AI description), but does NOT render its own
UI. The generic extraction engine (``engine.py``) renders confidence display,
inline editing, preview, and export uniformly for every processor.

This is what makes every platform feature — confidence, editable fields,
re-export, preview, validation, classification, multi-upload, downloads — work
automatically for any future processor: a new processor only declares a
``ProcessorSpec``; it inherits all behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FieldKind(str, Enum):
    """Editor type for a field, driving the input widget the engine renders."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOL = "bool"
    LONG_TEXT = "long_text"


@dataclass(frozen=True)
class FieldSpec:
    """Declarative description of a single scalar field.

    Attributes:
        path: Dotted path into the JSON document (e.g. ``"purchase_order.po_number"``).
        label: Human-readable label shown in the UI.
        kind: Editor kind, controls which input widget is rendered.
    """

    path: str
    label: str
    kind: FieldKind = FieldKind.TEXT


@dataclass(frozen=True)
class SectionSpec:
    """A titled group of fields shown together.

    Attributes:
        title: Section heading.
        fields: Ordered fields in this section.
    """

    title: str
    fields: list[FieldSpec]


@dataclass(frozen=True)
class LineItemColumn:
    """A column definition for the editable line-item table.

    Attributes:
        key: Key within each line-item dict.
        label: Column header.
        kind: Editor kind for the column.
    """

    key: str
    label: str
    kind: FieldKind = FieldKind.TEXT


@dataclass(frozen=True)
class ProcessorSpec:
    """Full declarative specification of a document processor.

    Attributes:
        use_case_key: Stable use-case key (matches the registry / UseCase).
        document_type: Human-readable document type name.
        department_key: Department this processor belongs to.
        keywords: Lowercase keywords used by the classifier as a fallback signal.
        ai_description: Natural-language description used by the AI classifier.
        sections: Ordered scalar sections for the editable summary.
        line_items_path: Dotted path to the line-item list (or None).
        line_item_columns: Column specs for the line-item table.
        json_suffix: Output filename suffix (e.g. ``"output"``, ``"shipping_bill"``).
    """

    use_case_key: str
    document_type: str
    department_key: str
    keywords: list[str] = field(default_factory=list)
    ai_description: str = ""
    sections: list[SectionSpec] = field(default_factory=list)
    line_items_path: str | None = None
    line_item_columns: list[LineItemColumn] = field(default_factory=list)
    json_suffix: str = "output"


# ----- Dotted-path helpers used by the engine ---------------------------- #


def get_path(data: dict[str, Any], path: str) -> Any:
    """Return the value at a dotted path, or None if any segment is missing."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def set_path(data: dict[str, Any], path: str, value: Any) -> None:
    """Set the value at a dotted path, creating intermediate dicts as needed."""
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        nxt = current.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            current[part] = nxt
        current = nxt
    current[parts[-1]] = value
