"""Generic document processing engine.

The engine renders extraction, field-level confidence, inline editing,
re-export, preview, and validation for ANY processor — driven entirely by the
processor's :class:`~processors.spec.ProcessorSpec`. No feature is hardcoded for
a specific document type; adding a new processor automatically inherits all of
this behaviour.

The engine never calls Gemini during editing or re-export. Extraction happens
once per uploaded document (in ``app.py`` orchestration); thereafter the edited
data in :class:`~document_state.DocumentState` is the single source of truth.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import streamlit as st

import ui
from document_state import DocumentState
from preview import render_document
from processors.spec import (
    FieldKind,
    FieldSpec,
    ProcessorSpec,
    get_path,
    set_path,
)
from utils.confidence import band, field_score

logger = logging.getLogger(__name__)


def render_document_workspace(doc: DocumentState) -> None:
    """Render the full review workspace for one extracted document.

    Args:
        doc: The document state to render (must be supported and extracted).
    """
    if not doc.supported or doc.data is None:
        st.warning("This document could not be processed.")
        return

    spec = doc.processor.spec

    # Original document vs extracted data toggle (feature 9).
    tab_data, tab_doc = st.tabs(["📝 Extracted Data", "📄 Original Document"])

    with tab_doc:
        _render_preview(doc)

    with tab_data:
        ui.confidence_legend()
        _render_validation(doc)
        _render_summary(doc, spec)
        _render_line_items(doc, spec)
        with st.expander("🧾 Raw JSON"):
            st.json(doc.data)
        _render_export(doc)


# ----- Preview ----------------------------------------------------------- #


def _render_preview(doc: DocumentState) -> None:
    """Render page thumbnails and the full document preview."""
    rendered = render_document(doc.file_bytes, doc.mime_type)
    if not rendered.pages:
        st.info("No preview available for this file type.")
        return

    if rendered.is_image:
        st.image(rendered.pages[0], use_container_width=True)
        return

    page_count = len(rendered.pages)
    if page_count > 1:
        st.caption(f"{page_count} pages")
        cols = st.columns(min(page_count, 6))
        for index, thumb in enumerate(rendered.thumbnails):
            with cols[index % len(cols)]:
                st.image(thumb, caption=f"Page {index + 1}", use_container_width=True)
        page_no = st.number_input(
            "View page", min_value=1, max_value=page_count, value=1,
            key=f"{doc.doc_id}_page",
        )
        st.image(rendered.pages[int(page_no) - 1], use_container_width=True)
    else:
        st.image(rendered.pages[0], use_container_width=True)


# ----- Validation -------------------------------------------------------- #


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


# ----- Editable summary (confidence-coloured) ---------------------------- #


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

    ui.section_heading("Line Items")
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
    """Render JSON and Excel download buttons for this document.

    Re-export uses the current (edited) data — Gemini is never called again.
    """
    ui.section_heading("⬇️ Export")
    col_json, col_excel = st.columns(2)
    with col_json:
        st.download_button(
            "⬇️ Download JSON",
            data=doc.json_bytes(),
            file_name=doc.json_filename(),
            mime="application/json",
            use_container_width=True,
            key=f"{doc.doc_id}:dl_json",
        )
    with col_excel:
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
