"""Generic document processing engine (review workspace).

The engine renders the review experience for ANY processor — driven entirely by
the processor's :class:`~processors.spec.ProcessorSpec`. No feature is hardcoded
for a specific document type; adding a new processor inherits all of this.

V2.3 review is a **split workspace**: an Acrobat-style PDF viewer on the left
(confidence-coloured overlay boxes + click-to-scroll), and the editable business
fields on the right, with a SAP-readiness badge and a single stronger-model
retry. The viewer and the fields share one confidence heatmap palette.

The engine never calls the AI during editing or re-export; extraction happens
once (or once more via the single retry). Thereafter the edited data in
:class:`~document_state.DocumentState` is the single source of truth.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import streamlit as st

import field_locator
import pdf_viewer
import ui
from config import ai_gateway
from document_state import DocumentState
from processing import retry_extract_document
from processors.spec import (
    FieldKind,
    FieldSpec,
    ProcessorSpec,
    get_path,
    set_path,
)
from utils.confidence import band, field_score, overall_confidence, summarize

logger = logging.getLogger(__name__)

_NONE_CHOICE = "— none —"


def _dev_mode() -> bool:
    """True when Developer Mode is active (raw JSON / audit are dev-only)."""
    return bool(st.session_state.get("dev_mode", False))


def _scalar_fields(spec: ProcessorSpec) -> list[FieldSpec]:
    """Flatten all scalar fields declared across the spec's sections."""
    return [f for section in spec.sections for f in section.fields]


def render_document_workspace(doc: DocumentState) -> None:
    """Render the full split review workspace for one extracted document."""
    if not doc.supported or doc.data is None:
        st.warning("This document could not be processed.")
        return

    spec = doc.processor.spec
    pages, sizes, boxes = _locations(doc, spec)
    focus = st.session_state.get(f"focus:{doc.doc_id}")

    left, right = st.columns([5, 4], gap="large")

    with left:
        ui.section_heading("📄 Original Document")
        if pages:
            pdf_viewer.render_viewer(
                pages,
                sizes,
                boxes,
                doc.confidence,
                labels={f.path: f.label for f in _scalar_fields(spec)},
                focus_path=focus,
                height=820,
            )
        else:
            st.info("No preview available for this file type.")

    with right:
        _render_overall_confidence(doc)
        ui.sap_badge(doc.sap)
        _render_retry(doc)
        _render_locate_controls(doc, spec, boxes)
        ui.confidence_legend()
        ui.render_autofix_notes(doc.autofix_notes)
        _render_validation(doc)
        _render_summary(doc, spec)

    # Wide areas render full-width below the split.
    _render_line_items(doc, spec)
    if _dev_mode():
        _render_developer_panels(doc)
    _render_export(doc)


# ----- Field location (hybrid) ------------------------------------------- #


def _scalar_values(doc: DocumentState, spec: ProcessorSpec) -> dict[str, Any]:
    """Current non-empty scalar values keyed by dotted path (for locating)."""
    values: dict[str, Any] = {}
    for fspec in _scalar_fields(spec):
        value = get_path(doc.data, fspec.path)
        if value not in (None, "", [], {}):
            values[fspec.path] = value
    return values


def _locations(
    doc: DocumentState, spec: ProcessorSpec
) -> tuple[list[bytes], list[tuple[int, int]], dict[str, list[dict[str, float]]]]:
    """Return (pages, sizes, boxes), rendering + text-locating once per session."""
    pages_key = f"pages:{doc.doc_id}"
    if pages_key not in st.session_state:
        st.session_state[pages_key] = pdf_viewer.render_pages(doc.file_bytes, doc.mime_type)
    pages, sizes = st.session_state[pages_key]

    loc_key = f"loc:{doc.doc_id}"
    if loc_key not in st.session_state:
        st.session_state[loc_key] = field_locator.locate(
            doc.file_bytes, doc.mime_type, _scalar_values(doc, spec)
        )
    return pages, sizes, st.session_state[loc_key]


def _render_locate_controls(
    doc: DocumentState, spec: ProcessorSpec, boxes: dict[str, list[dict[str, float]]]
) -> None:
    """Render the field-focus selector and the on-demand AI locate action."""
    fields = _scalar_fields(spec)
    labels = {f.path: f.label for f in fields}
    located = set(boxes.keys())
    options = [_NONE_CHOICE] + [f.path for f in fields]
    current = st.session_state.get(f"focus:{doc.doc_id}") or _NONE_CHOICE
    index = options.index(current) if current in options else 0

    def _fmt(path: str) -> str:
        if path == _NONE_CHOICE:
            return _NONE_CHOICE
        marker = "📍" if path in located else "○"
        return f"{marker} {labels.get(path, path)}"

    choice = st.selectbox(
        "🔎 Highlight a field on the document",
        options,
        index=index,
        format_func=_fmt,
        key=f"{doc.doc_id}:focussel",
    )
    new_focus = None if choice == _NONE_CHOICE else choice
    if new_focus != st.session_state.get(f"focus:{doc.doc_id}"):
        st.session_state[f"focus:{doc.doc_id}"] = new_focus
        st.rerun()

    unlocated = [
        f.path
        for f in fields
        if f.path not in located and get_path(doc.data, f.path) not in (None, "", [], {})
    ]
    if unlocated:
        if st.button(
            f"✨ Locate {len(unlocated)} remaining field(s) with AI",
            key=f"{doc.doc_id}:ailoc",
            use_container_width=True,
            help="Uses the AI gateway to find fields text-search could not locate.",
        ):
            _ai_locate(doc, spec, unlocated)
            st.rerun()


def _ai_locate(doc: DocumentState, spec: ProcessorSpec, unlocated: list[str]) -> None:
    """Augment located boxes with AI bounding boxes for unlocated fields."""
    pages_key = f"pages:{doc.doc_id}"
    pages, sizes = st.session_state.get(
        pages_key, pdf_viewer.render_pages(doc.file_bytes, doc.mime_type)
    )
    if not pages:
        return
    if doc.mime_type == "application/pdf":
        parts = [(png, "image/png") for png in pages]
    else:
        parts = [(pages[0], doc.mime_type)]
    labels = {f.path: f.label for f in _scalar_fields(spec)}
    values = {p: get_path(doc.data, p) for p in unlocated}
    with st.spinner("Locating fields with AI…"):
        ai_boxes = field_locator.locate_with_ai(values, parts, sizes, labels=labels)
    merged = dict(st.session_state.get(f"loc:{doc.doc_id}", {}))
    merged.update(ai_boxes)
    st.session_state[f"loc:{doc.doc_id}"] = merged
    if ai_boxes:
        st.success(f"Located {len(ai_boxes)} additional field(s).")
    else:
        st.info("The AI could not confidently locate the remaining fields.")


# ----- Retry (single, stronger model) ------------------------------------ #


def _render_retry(doc: DocumentState) -> None:
    """Render the single stronger-model retry control (one retry per document)."""
    if doc.retry_message:
        if doc.retry_message.startswith("Re-extracted"):
            st.success(doc.retry_message)
        else:
            st.warning(doc.retry_message)

    if st.button(
        f"↻ Retry with stronger model ({ai_gateway.retry_model})",
        disabled=doc.retry_used,
        key=f"{doc.doc_id}:retry",
        use_container_width=True,
        help="Re-runs extraction once on the RETRY model. Only replaces data if it succeeds.",
    ):
        with st.spinner(f"Re-extracting with {ai_gateway.retry_model}…"):
            retry_extract_document(doc)
        # Data may have changed — refresh locations and re-render.
        st.session_state.pop(f"loc:{doc.doc_id}", None)
        st.rerun()


# ----- Confidence / validation ------------------------------------------- #


def _render_overall_confidence(doc: DocumentState) -> None:
    """Render the prominent overall document confidence badge + band breakdown."""
    score = overall_confidence(doc.confidence)
    ui.overall_confidence_badge(score, band(score), summarize(doc.confidence))


def _render_validation(doc: DocumentState) -> None:
    """Re-run validation on the current (possibly edited) data and show it."""
    issues = doc.processor.validate(doc.data)
    doc.issues = issues
    if issues:
        with st.expander(f"⚠️ Validation: {len(issues)} issue(s)", expanded=True):
            for issue in issues:
                st.warning(issue)
    else:
        st.markdown(
            '<div class="igl-queue-row" style="background:rgba(34,197,94,0.10);'
            'border-color:rgba(34,197,94,0.35);margin-bottom:14px;">'
            '<span class="igl-check">✓</span>'
            '<div class="igl-queue-name" style="color:#22C55E;">Validation passed</div>'
            "</div>",
            unsafe_allow_html=True,
        )


def _render_developer_panels(doc: DocumentState) -> None:
    """Render developer-only panels: raw JSON and the reviewer edit audit trail."""
    audit = doc.build_audit()
    if audit:
        with st.expander(f"📝 Audit trail: {len(audit)} edited field(s)"):
            st.dataframe(audit, use_container_width=True, hide_index=True)
    with st.expander("🧾 Raw JSON (developer)"):
        st.json(doc.data)


# ----- Editable summary (confidence-coloured heatmap) -------------------- #


def _render_summary(doc: DocumentState, spec: ProcessorSpec) -> None:
    """Render editable, confidence-coloured scalar fields from the spec."""
    data = doc.data
    for section in spec.sections:
        ui.section_heading(section.title)
        columns = st.columns(2)
        for index, fspec in enumerate(section.fields):
            with columns[index % 2]:
                _render_field(doc, data, fspec)


def _render_field(doc: DocumentState, data: dict[str, Any], fspec: FieldSpec) -> None:
    """Render one confidence-labelled, editable field and write edits back."""
    score = field_score(doc.confidence, fspec.path)
    ui.field_label(fspec.label, score, band(score))

    value = get_path(data, fspec.path)
    key = f"{doc.doc_id}:{fspec.path}"

    if fspec.kind == FieldKind.NUMBER:
        new_value: Any = st.number_input(
            fspec.label, value=_as_float(value), step=1.0,
            key=key, label_visibility="collapsed",
        )
    elif fspec.kind == FieldKind.BOOL:
        new_value = st.checkbox(
            fspec.label, value=bool(value), key=key, label_visibility="collapsed",
        )
    elif fspec.kind == FieldKind.LONG_TEXT:
        new_value = st.text_area(
            fspec.label, value=_as_text(value), height=80,
            key=key, label_visibility="collapsed",
        )
    else:
        new_value = st.text_input(
            fspec.label, value=_as_text(value),
            key=key, label_visibility="collapsed",
        )

    set_path(data, fspec.path, new_value)


# ----- Editable line items ----------------------------------------------- #


def _render_line_items(doc: DocumentState, spec: ProcessorSpec) -> None:
    """Render the editable line-item table when the spec declares one."""
    if not spec.line_items_path:
        return
    items = get_path(doc.data, spec.line_items_path) or []

    ui.section_heading("📋 Line Items")
    if spec.line_item_columns:
        column_order = [c.key for c in spec.line_item_columns]
        frame = pd.DataFrame(items)
        for col in column_order:
            if col not in frame.columns:
                frame[col] = None
        frame = frame[column_order]
    else:
        frame = pd.DataFrame(items)

    edited = st.data_editor(
        frame,
        num_rows="dynamic",
        use_container_width=True,
        key=f"{doc.doc_id}:line_items",
    )
    set_path(doc.data, spec.line_items_path, edited.to_dict(orient="records"))


# ----- Per-document export (re-export, no AI) ---------------------------- #


def _render_export(doc: DocumentState) -> None:
    """Render Excel (and, in Developer Mode, JSON) download buttons."""
    ui.section_heading("⬇️ Export")
    columns = st.columns(2) if _dev_mode() else [st.container()]
    with columns[0]:
        try:
            st.download_button(
                "⬇️ Download Excel",
                data=doc.excel_bytes(),
                file_name=doc.excel_filename(),
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
                key=f"{doc.doc_id}:dl_excel",
            )
        except Exception as exc:  # noqa: BLE001 - surface export errors in UI
            logger.exception("Excel generation failed.")
            st.error(f"Excel generation failed: {exc}")
    if _dev_mode():
        with columns[1]:
            st.download_button(
                "⬇️ Download JSON (developer)",
                data=doc.json_bytes(),
                file_name=doc.json_filename(),
                mime="application/json",
                use_container_width=True,
                key=f"{doc.doc_id}:dl_json",
            )


# ----- Coercion helpers -------------------------------------------------- #


def _as_text(value: Any) -> str:
    """Coerce a value to a display string (None → empty)."""
    return "" if value is None else str(value)


def _as_float(value: Any) -> float:
    """Coerce a value to float, defaulting to 0.0."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
