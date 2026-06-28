"""Streamlit application entry point for the Document Intelligence Platform.

Workflow (Version 1.2):

    Select Department
        -> Upload one or more documents
        -> AI auto-classifies each document and routes it to the right processor
        -> Generic engine renders confidence-scored, editable extraction
        -> Re-export JSON / Excel per document, or batch download all / ZIP

This module is the orchestration shell only. All document-specific behaviour
lives behind the processor registry + generic engine, so every feature works
automatically for any processor added in the future.
"""

from __future__ import annotations

import hashlib
import logging
import time

import streamlit as st

import config
import ui
from config import has_gemini_keys, settings
from departments import DEPARTMENTS, Department
from document_state import DocumentManager, DocumentState
from engine import render_document_workspace
from processing import (
    build_classifier,
    classify_document,
    extract_document,
)
from processors.bootstrap import bootstrap_processors
from processors.registry import all_processors, processors_for_department
from utils.file_handler import guess_mime_type
from utils.helpers import configure_logging

configure_logging()
bootstrap_processors()
logger = logging.getLogger(__name__)

_SUPPORTED_TYPES = ["pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"]


def _manager() -> DocumentManager:
    """Return the session-scoped document manager, creating it if needed."""
    if "doc_manager" not in st.session_state:
        st.session_state["doc_manager"] = DocumentManager()
    return st.session_state["doc_manager"]


def _render_sidebar() -> Department:
    """Render the department navigation (document type is auto-detected)."""
    with st.sidebar:
        ui.render_sidebar_brand(settings.assets_dir)
        st.divider()

        dept_names = [f"{d.icon}  {d.name}" for d in DEPARTMENTS]
        dept_index = st.selectbox(
            "Department",
            options=range(len(DEPARTMENTS)),
            format_func=lambda i: dept_names[i],
            index=0,
        )
        department = DEPARTMENTS[dept_index]

        st.caption("📑 Document type is detected automatically on upload.")

        manager = _manager()
        if manager.documents:
            st.divider()
            st.metric("Documents", len(manager.documents))
            if st.button("Clear all", use_container_width=True):
                manager.clear()
                st.rerun()

        # Development-only AI Gateway status (hidden in production; no key
        # values). Shows the current model, key number, retries, and health.
        if settings.dev_mode and config.ai_gateway.has_capacity():
            st.divider()
            ui.render_gateway_status(config.ai_gateway.status())

    return department


def _doc_id_for(filename: str, payload: bytes) -> str:
    """Stable per-document id based on name + content hash."""
    digest = hashlib.sha1(payload).hexdigest()[:10]
    return f"{filename}:{digest}"


def _process_uploads(department: Department, uploaded_files: list) -> None:
    """Classify and extract each uploaded document with a progress indicator."""
    manager = _manager()

    # Key health is managed per-request by the AI gateway (it reconsiders every
    # key and model on each call), so no batch-level reset is needed here.
    classifier = build_classifier()

    # Department-scoped candidates first; fall back to all processors so a
    # mis-filed document can still be detected.
    candidates = processors_for_department(department.key) or all_processors()

    ui.section_heading("⚡ Processing Queue")
    progress = st.progress(0.0, text="Starting…")
    total = len(uploaded_files)

    for index, uploaded in enumerate(uploaded_files, start=1):
        payload = uploaded.getvalue()
        doc_id = _doc_id_for(uploaded.name, payload)
        if manager.has(doc_id):
            progress.progress(index / total, text=f"Skipped {uploaded.name} (already processed)")
            continue

        try:
            mime_type = guess_mime_type(uploaded.name)
        except ValueError as exc:
            logger.warning("Unsupported upload %s: %s", uploaded.name, exc)
            continue

        doc = DocumentState(
            doc_id=doc_id,
            filename=uploaded.name,
            file_bytes=payload,
            mime_type=mime_type,
        )

        started = time.perf_counter()
        progress.progress((index - 0.5) / total, text=f"Classifying {uploaded.name}…")
        classify_document(doc, classifier, candidates)

        if doc.supported:
            progress.progress((index - 0.25) / total, text=f"Extracting {uploaded.name}…")
            extract_document(doc)

        # Record processing time so the queue / document cards can display it.
        st.session_state.setdefault("doc_times", {})[doc_id] = time.perf_counter() - started

        manager.add(doc)
        progress.progress(index / total, text=f"Processed {uploaded.name}")

    progress.empty()


def _doc_seconds(doc_id: str) -> float | None:
    """Return the recorded processing time (seconds) for a document, if any."""
    return st.session_state.get("doc_times", {}).get(doc_id)


def _render_processing_queue() -> None:
    """Render a premium queue summarizing every processed document."""
    manager = _manager()
    docs = manager.documents
    if not docs:
        return

    ui.section_heading("📥 Processing Queue")
    for doc in docs:
        icon = ui.status_icon(doc.status)
        seconds = _doc_seconds(doc.doc_id)
        timing = f"{seconds:.1f} sec" if seconds is not None else "—"

        if doc.status == "done":
            right = '<span class="igl-check">✓</span>'
            state = f"Completed · {timing}"
        elif doc.status == "unsupported":
            right = '<span class="igl-queue-meta">Unsupported</span>'
            state = "Skipped"
        elif doc.status == "error":
            right = '<span class="igl-queue-meta">Failed</span>'
            state = "Error"
        else:
            right = '<span class="igl-queue-meta">Pending</span>'
            state = "Queued"

        st.markdown(
            f'<div class="igl-queue-row">'
            f'<span class="igl-queue-ico">{icon}</span>'
            f'<div style="flex:1;">'
            f'<div class="igl-queue-name">{doc.filename}</div>'
            f'<div class="igl-queue-meta">{state}</div>'
            f"</div>{right}</div>",
            unsafe_allow_html=True,
        )


def _render_batch_downloads() -> None:
    """Render Download All JSON / Excel / ZIP for processed documents."""
    manager = _manager()
    processed = manager.processed
    if len(processed) < 1:
        return

    ui.section_heading("📦 Batch Export")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "⬇️ Download All JSON",
            data=manager.all_json_zip(),
            file_name="all_json.zip",
            mime="application/zip",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "⬇️ Download All Excel",
            data=manager.all_excel_zip(),
            file_name="all_excel.zip",
            mime="application/zip",
            use_container_width=True,
        )
    with c3:
        st.download_button(
            "⬇️ Download ZIP (JSON + Excel)",
            data=manager.full_zip(),
            file_name="all_documents.zip",
            mime="application/zip",
            use_container_width=True,
        )


def _render_documents() -> None:
    """Render one tab per uploaded document, driven by the generic engine."""
    manager = _manager()
    docs = manager.documents
    if not docs:
        st.info("Upload one or more documents and click **Process Documents**.")
        return

    ui.section_heading("📄 Documents")
    labels = [f"{ui.status_icon(doc.status)} {doc.filename}" for doc in docs]

    tabs = st.tabs(labels)
    for tab, doc in zip(tabs, docs):
        with tab:
            _render_document_header(doc)
            if doc.status == "unsupported":
                st.error("Unsupported document type.")
            elif doc.status == "error":
                st.error(f"Extraction failed: {doc.error}")
            elif doc.status == "done":
                render_document_workspace(doc)
            else:
                st.info("This document has not been processed yet.")


def _render_document_header(doc: DocumentState) -> None:
    """Render the premium classification summary card for a document."""
    method = "AI" if doc.classification_method == "ai" else "Keywords"
    score = doc.classification_confidence
    band_name = _cls_band(score)
    seconds = _doc_seconds(doc.doc_id)
    timing = f" · {seconds:.1f} sec" if seconds is not None else ""

    st.markdown(
        f'<div class="igl-doc-head">'
        f'<div class="igl-doc-icon">{ui.status_icon(doc.status)}</div>'
        f'<div style="flex:1;min-width:200px;">'
        f'<div class="igl-card-title" style="margin-bottom:4px;">Detected Document Type</div>'
        f'<div class="igl-doc-type">{doc.document_type}</div>'
        f'<div class="igl-doc-meta">Classified via {method}{timing}</div>'
        f'</div>'
        f'<div style="min-width:160px;">'
        f'{ui.confidence_chip(score, band_name)}'
        f'{ui.confidence_meter(score, band_name)}'
        f'</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _cls_band(score: int) -> str:
    """Confidence band for the classification score."""
    from utils.confidence import band

    return band(score)


def main() -> None:
    """Run the India Glycols Document Intelligence Platform."""
    st.set_page_config(
        page_title="India Glycols · Document Intelligence Platform",
        page_icon="🧪",
        layout="wide",
    )
    ui.inject_theme()
    ui.render_header(settings.assets_dir)

    department = _render_sidebar()
    ui.render_breadcrumb(department.name, "Auto-detect document type")

    if not has_gemini_keys():
        st.error(
            "No Gemini API key is configured. Add GEMINI_API_KEY (or "
            "GEMINI_API_KEY_1, GEMINI_API_KEY_2, ...) to the .env file and "
            "restart the application."
        )

    _render_upload_hint()
    uploaded_files = st.file_uploader(
        f"Upload documents for {department.name} (PDF or image)",
        type=_SUPPORTED_TYPES,
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files and st.button("⚡ Process Documents", type="primary"):
        _process_uploads(department, uploaded_files)

    _render_processing_queue()
    _render_batch_downloads()
    _render_documents()


def _render_upload_hint() -> None:
    """Render the premium, centered drag-and-drop hint above the uploader."""
    types = ["Purchase Orders", "Invoices", "Shipping Bills", "Scanned PDFs", "Images"]
    chips = "".join(f"<span>{t}</span>" for t in types)
    st.markdown(
        f'<div class="igl-upload-hint">'
        f'<div class="glyph">📄</div>'
        f'<div class="ttl">Drop Documents Here</div>'
        f'<div class="types">{chips}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
