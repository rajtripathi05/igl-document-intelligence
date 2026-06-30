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


#: Processor lifecycle states. ``production`` is visible to business users;
#: ``coming_soon`` renders the "coming soon" placeholder in business mode;
#: ``testing`` / ``draft`` are visible only in Developer / Admin mode.
PRODUCTION = "production"
TESTING = "testing"
DRAFT = "draft"
COMING_SOON = "coming_soon"
VALID_STATUSES = frozenset({PRODUCTION, TESTING, DRAFT, COMING_SOON})


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
    required: bool = False


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
class ExportColumn:
    """A single column in the consolidated one-row-per-document register.

    Attributes:
        header: Column header text (matches the uploaded business template).
        path: Dotted path into the document JSON. Paths beginning with the
            processor's ``line_items_path`` are resolved across line items
            according to ``agg``.
        agg: Aggregation for list-valued paths: ``"first"`` (default), ``"sum"``,
            or ``"join"`` (comma-separated unique values).
    """

    header: str
    path: str
    agg: str = "first"


@dataclass(frozen=True)
class ExportSpec:
    """Declarative mapping that builds one register row per document.

    Attributes:
        columns: Ordered register columns.
        template: Optional path (relative to the processor folder) to a styled
            Excel template whose header styling/widths/merges are reused.
        sheet: Worksheet name within the template (or the new sheet's title).
        header_row: 1-based row index of the header in the template.
        start_row: 1-based row index at which data rows begin.
        template_version: Optional detected/declared template version label.
    """

    columns: list[ExportColumn] = field(default_factory=list)
    template: str | None = None
    sheet: str = "Register"
    header_row: int = 1
    start_row: int = 2
    template_version: str = ""


@dataclass(frozen=True)
class ProcessorSpec:
    """Full declarative specification of a document processor.

    Attributes:
        use_case_key: Stable use-case key (matches the registry / folder name).
        document_type: Human-readable document type name (business label).
        department_key: Department this processor belongs to.
        keywords: Lowercase keywords used by the classifier as a fallback signal.
        ai_description: Natural-language description used by the AI classifier.
        sections: Ordered scalar sections for the editable summary.
        line_items_path: Dotted path to the line-item list (or None).
        line_item_columns: Column specs for the line-item table.
        json_suffix: Output filename suffix (e.g. ``"output"``, ``"shipping_bill"``).
        business_process: Business-process label shown in navigation.
        status: Lifecycle state (see module constants).
        department_name: Human-readable department name.
        department_icon: Department icon/emoji.
        department_order: Sort order of the department in navigation.
        export: Register export mapping, or None to use a generic per-doc export.
        prompt_version: Prompt set version folder (e.g. ``"v1"``); flat prompts
            are used when the versioned folder is absent.
        manifest_version / processor_version / schema_version: Version stamps for
            safe evolution.
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
    business_process: str = ""
    status: str = PRODUCTION
    accuracy: int | None = None
    department_name: str = ""
    department_icon: str = "🏢"
    department_order: int = 100
    export: ExportSpec | None = None
    prompt_version: str = "v1"
    manifest_version: str = "1.0"
    processor_version: str = "1.0"
    schema_version: str = "1.0"

    @property
    def active(self) -> bool:
        """True when the processor is live for business users (production)."""
        return self.status == PRODUCTION

    @property
    def coming_soon(self) -> bool:
        """True when the processor is a declared-but-unbuilt placeholder."""
        return self.status == COMING_SOON

    @classmethod
    def from_manifest(cls, manifest: dict[str, Any]) -> "ProcessorSpec":
        """Build a :class:`ProcessorSpec` from a parsed ``manifest.json`` dict.

        The manifest is the single source of processor metadata; every field is
        optional except ``key`` so that a minimal "coming soon" manifest is
        enough to surface a process in navigation.

        Args:
            manifest: Parsed manifest dictionary.

        Returns:
            A fully-populated, frozen :class:`ProcessorSpec`.

        Raises:
            ValueError: If the manifest has no ``key``.
        """
        key = (manifest.get("key") or "").strip()
        if not key:
            raise ValueError("Manifest must define a non-empty 'key'.")

        department = manifest.get("department") or {}
        sections = [
            SectionSpec(
                title=section.get("title", ""),
                fields=[
                    FieldSpec(
                        path=f["path"],
                        label=f.get("label", f["path"]),
                        kind=FieldKind(f.get("kind", "text")),
                        required=bool(f.get("required", False)),
                    )
                    for f in section.get("fields", [])
                ],
            )
            for section in manifest.get("sections", [])
        ]

        line_items = manifest.get("line_items") or {}
        line_items_path = line_items.get("path")
        line_item_columns = [
            LineItemColumn(
                key=c["key"],
                label=c.get("label", c["key"]),
                kind=FieldKind(c.get("kind", "text")),
            )
            for c in line_items.get("columns", [])
        ]

        export = None
        export_manifest = manifest.get("export")
        if export_manifest and export_manifest.get("columns"):
            export = ExportSpec(
                columns=[
                    ExportColumn(
                        header=col.get("header", col["path"]),
                        path=col["path"],
                        agg=col.get("agg", "first"),
                    )
                    for col in export_manifest["columns"]
                ],
                template=export_manifest.get("template"),
                sheet=export_manifest.get("sheet", "Register"),
                header_row=int(export_manifest.get("header_row", 1)),
                start_row=int(export_manifest.get("start_row", 2)),
                template_version=export_manifest.get("template_version", ""),
            )

        status = manifest.get("status", PRODUCTION)
        if status not in VALID_STATUSES:
            status = PRODUCTION

        return cls(
            use_case_key=key,
            document_type=manifest.get("document_type", key.replace("_", " ").title()),
            department_key=department.get("key", ""),
            keywords=[str(k).lower() for k in manifest.get("keywords", [])],
            ai_description=manifest.get("ai_description", ""),
            sections=sections,
            line_items_path=line_items_path,
            line_item_columns=line_item_columns,
            json_suffix=manifest.get("json_suffix", key),
            business_process=manifest.get("business_process", manifest.get("document_type", "")),
            status=status,
            accuracy=_optional_int(manifest.get("accuracy")),
            department_name=department.get("name", ""),
            department_icon=department.get("icon", "🏢"),
            department_order=int(department.get("order", 100)),
            export=export,
            prompt_version=manifest.get("prompt_version", "v1"),
            manifest_version=str(manifest.get("manifest_version", "1.0")),
            processor_version=str(manifest.get("processor_version", "1.0")),
            schema_version=str(manifest.get("schema_version", "1.0")),
        )


# ----- Dotted-path helpers used by the engine ---------------------------- #


def _optional_int(value: Any) -> int | None:
    """Coerce a manifest value to an int, or None when absent/unparseable."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


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


def resolve_export_value(
    data: dict[str, Any], column: "ExportColumn", line_items_path: str | None
) -> Any:
    """Resolve a register cell value for ``column`` from ``data``.

    Scalar dotted paths resolve directly. Paths that point inside the
    processor's line-item list (``"<line_items_path>.<field>"``) are resolved
    across all line items and aggregated by ``column.agg``:

    - ``"first"``: the first non-empty value (default),
    - ``"sum"``: numeric sum of the values,
    - ``"join"``: comma-separated unique non-empty values.

    Args:
        data: The normalized document data.
        column: The export column to resolve.
        line_items_path: The processor's line-item list path (or None).

    Returns:
        The resolved scalar value (``None`` when absent).
    """
    path = column.path
    if line_items_path and (
        path == line_items_path or path.startswith(line_items_path + ".")
    ):
        items = get_path(data, line_items_path) or []
        if not isinstance(items, list):
            return None
        field_key = path[len(line_items_path) + 1:] if path != line_items_path else ""
        values = []
        for item in items:
            if not isinstance(item, dict):
                continue
            value = item.get(field_key) if field_key else item
            if value not in (None, ""):
                values.append(value)
        if not values:
            return None
        if column.agg == "sum":
            total = 0.0
            for value in values:
                try:
                    total += float(value)
                except (TypeError, ValueError):
                    continue
            return total
        if column.agg == "join":
            seen: list[str] = []
            for value in values:
                text = str(value)
                if text not in seen:
                    seen.append(text)
            return ", ".join(seen)
        return values[0]

    return get_path(data, path)
