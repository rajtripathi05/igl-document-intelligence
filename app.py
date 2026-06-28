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
        st.markdown(f"### {ui.COMPANY_NAME}")
        st.caption("Document Intelligence Platform")
        st.divider()

        dept_names = [f"{d.icon}  {d.name}" for d in DEPARTMENTS]
        dept_index = st.selectbox(
            "Department",
            options=range(len(DEPARTMENTS)),
            format_func=lambda i: dept_names[i],
            index=0,
        )
        department = DEPARTMENTS[dept_index]

        st.divider()
        st.caption("📑 Document type is detected automatically on upload.")

        manager = _manager()
        if manager.documents:
            st.divider()
            st.metric("Documents", len(manager.documents))
            if st.button("Clear all", use_container_width=True):
                manager.clear()
                st.rerun()

        # Development-only Gemini key status (hidden in production; no key values).
        if settings.dev_mode and config.gemini_key_manager.has_keys():
            st.divider()
            ui.render_key_status(config.gemini_key_manager.status())

    return department


def _doc_id_for(filename: str, payload: bytes) -> str:
    """Stable per-document id based on name + content hash."""
    digest = hashlib.sha1(payload).hexdigest()[:10]
    return f"{filename}:{digest}"


def _process_uploads(department: Department, uploaded_files: list) -> None:
    """Classify and extract each uploaded document with a progress indicator."""
    manager = _manager()

    # A new processing action is a fresh attempt: clear any key-exhaustion flags
    # from a previous run so every key is reconsidered. Keys that hit a rate
    # limit during THIS batch stay skipped for the remainder of the batch.
    config.gemini_key_manager.reset_health()

    classifier = build_classifier()

    # Department-scoped candidates first; fall back to all processors so a
    # mis-filed document can still be detected.
    candidates = processors_for_department(department.key) or all_processors()

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

        progress.progress((index - 0.5) / total, text=f"Classifying {uploaded.name}…")
        classify_document(doc, classifier, candidates)

        if doc.supported:
            progress.progress((index - 0.25) / total, text=f"Extracting {uploaded.name}…")
            extract_document(doc)

        manager.add(doc)
        progress.progress(index / total, text=f"Processed {uploaded.name}")

    progress.empty()


def _render_batch_downloads() -> None:
    """Render Download All JSON / Excel / ZIP for processed documents."""
    manager = _manager()
    processed = manager.processed
    if len(processed) < 1:
        return

    st.markdown("### Batch Export")
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

    labels = []
    for doc in docs:
        if doc.status == "done":
            icon = "✅"
        elif doc.status == "unsupported":
            icon = "🚫"
        elif doc.status == "error":
            icon = "⚠️"
        else:
            icon = "⏳"
        labels.append(f"{icon} {doc.filename}")

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
    """Render the classification summary card for a document."""
    method = "AI" if doc.classification_method == "ai" else "Keywords"
    st.markdown(
        f'<div class="igl-card">'
        f'<div class="igl-card-title">Detected Document Type</div>'
        f'<span class="igl-doc-tab">{doc.document_type}</span>'
        f'  {ui.confidence_chip(doc.classification_confidence, _cls_band(doc.classification_confidence))}'
        f'  <span class="igl-metric-label">via {method}</span>'
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

    uploaded_files = st.file_uploader(
        f"Upload documents for {department.name} (PDF or image)",
        type=_SUPPORTED_TYPES,
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("Process Documents", type="primary"):
        _process_uploads(department, uploaded_files)

    _render_batch_downloads()
    _render_documents()


if __name__ == "__main__":
    main()
