"""Streamlit application entry point for the Enterprise Document Intelligence Platform.

Workflow (Version 2.0):

    Manual mode (default):
        Department -> Business Process -> Upload -> AI Processing -> Validation
        -> Auto-Fix -> Editable Review -> Excel Register

    Auto Detect mode (optional):
        Department -> Upload -> AI determines the business process -> ...

This module is the orchestration shell only. All document-specific behaviour
lives behind the manifest-driven processor registry + generic engine, so every
feature works automatically for any processor discovered from a folder.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass

import streamlit as st

import admin
import config
import consolidated_excel
import cost
import duplicates
import history
import ui
from config import has_ai_key, settings
from departments import DEPARTMENTS, Department
from document_state import DocumentManager, DocumentState
from engine import render_document_workspace
from processing import build_classifier, process_batch
from processors.base import BaseProcessor
from processors.bootstrap import bootstrap_processors
from processors.registry import (
    active_processors,
    all_processors,
    business_processes_for_department,
    production_processors_for_department,
)
from processors.spec import COMING_SOON, DRAFT, PRODUCTION, TESTING
from utils.file_handler import guess_mime_type
from utils.helpers import configure_logging

configure_logging()
bootstrap_processors()
logger = logging.getLogger(__name__)

_SUPPORTED_TYPES = ["pdf", "png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"]
_MODE_MANUAL = "Manual"
_MODE_AUTO = "Auto Detect"
_EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class Nav:
    """Resolved navigation state from the sidebar."""

    mode: str
    department: Department
    view: str
    dev_mode: bool


def _manager() -> DocumentManager:
    """Return the session-scoped document manager, creating it if needed."""
    if "doc_manager" not in st.session_state:
        st.session_state["doc_manager"] = DocumentManager()
    return st.session_state["doc_manager"]


# ----- Sidebar / navigation --------------------------------------------- #


@st.dialog("🔒 Developer Mode")
def _dev_password_dialog() -> None:
    """Modal password prompt that unlocks Developer Mode for the session.

    Developer Mode is never accessible without entering the correct admin
    password (resolved by ``config.verify_admin_password`` from the environment /
    Streamlit secrets, defaulting to the built-in value). The password itself is
    never displayed anywhere in the UI.
    """
    st.write(
        "Developer Mode is restricted to administrators. "
        "Enter the admin password to continue."
    )
    password = st.text_input("Admin password", type="password", key="dev_pw_input")
    if st.button("Unlock", type="primary", use_container_width=True):
        if config.verify_admin_password(password):
            st.session_state["dev_unlocked"] = True
            st.session_state["dev_mode"] = True
            st.session_state.pop("dev_pw_input", None)
            st.rerun()
        else:
            st.error("Incorrect Admin Password")


def _render_dev_gate() -> bool:
    """Render the password-gated Developer Mode control; return whether unlocked.

    Business users see only a locked "Developer Mode" button. Clicking it opens
    the password modal. Once unlocked, Developer Mode stays unlocked for the
    current Streamlit session until the user explicitly locks it again.
    """
    unlocked = bool(st.session_state.get("dev_unlocked", False))
    if unlocked:
        st.session_state["dev_mode"] = True
        st.markdown("🔓 **Developer Mode** · unlocked")
        if st.button("Lock Developer Mode", use_container_width=True):
            st.session_state["dev_unlocked"] = False
            st.session_state["dev_mode"] = False
            st.rerun()
        return True

    st.session_state["dev_mode"] = False
    st.caption("👤 Business mode")
    if st.button("🔒 Developer Mode", use_container_width=True):
        _dev_password_dialog()
    return False


def _render_sidebar() -> Nav:
    """Render the sidebar: mode, department, developer gate, and section nav."""
    with st.sidebar:
        ui.render_sidebar_brand(settings.assets_dir)
        st.divider()

        mode = st.radio(
            "Mode",
            [_MODE_MANUAL, _MODE_AUTO],
            index=0,
            help="Manual gives the highest accuracy. Auto Detect lets the AI "
            "choose the business process.",
        )

        dept_index = st.selectbox(
            "Department",
            options=range(len(DEPARTMENTS)),
            format_func=lambda i: f"{DEPARTMENTS[i].icon}  {DEPARTMENTS[i].name}",
            index=0,
        )
        department = DEPARTMENTS[dept_index]

        st.divider()
        dev_mode = _render_dev_gate()

        view = "process"
        if dev_mode:
            view_label = st.radio(
                "Section",
                ["Process Documents", "History", "Cost & Health", "Admin"],
                index=0,
            )
            view = {
                "Process Documents": "process",
                "History": "history",
                "Cost & Health": "cost",
                "Admin": "admin",
            }[view_label]

        manager = _manager()
        if manager.documents:
            st.divider()
            st.metric("Documents this session", len(manager.documents))
            if st.button("Clear all", use_container_width=True):
                manager.clear()
                st.rerun()

        if dev_mode and config.ai_gateway.has_capacity():
            st.divider()
            pending = sum(1 for d in manager.documents if d.status == "pending")
            ui.render_gateway_status(
                config.ai_gateway.status(), queue=pending, stage="Idle"
            )

    return Nav(mode=mode, department=department, view=view, dev_mode=dev_mode)


# ----- Upload + processing ---------------------------------------------- #


def _doc_id_for(filename: str, payload: bytes) -> str:
    """Stable per-document id based on name + content hash."""
    digest = hashlib.sha1(payload).hexdigest()[:10]
    return f"{filename}:{digest}"


def _build_doc_states(uploaded_files: list) -> list[DocumentState]:
    """Turn uploaded files into fresh DocumentStates (skipping duplicates)."""
    manager = _manager()
    docs: list[DocumentState] = []
    for uploaded in uploaded_files:
        payload = uploaded.getvalue()
        doc_id = _doc_id_for(uploaded.name, payload)
        if manager.has(doc_id):
            continue
        try:
            mime_type = guess_mime_type(uploaded.name)
        except ValueError as exc:
            logger.warning("Unsupported upload %s: %s", uploaded.name, exc)
            continue
        docs.append(
            DocumentState(
                doc_id=doc_id,
                filename=uploaded.name,
                file_bytes=payload,
                mime_type=mime_type,
            )
        )
    return docs


def _run_processing(
    nav: Nav,
    docs: list[DocumentState],
    processor: BaseProcessor | None,
) -> None:
    """Process a batch with a live progress bar, then store + record history."""
    if not docs:
        st.info("These documents were already processed in this session.")
        return

    manager = _manager()
    ui.section_heading("⚡ AI Processing Pipeline")
    gateway_status = (
        config.ai_gateway.status() if config.ai_gateway.has_capacity() else {}
    )
    theater = ui.ProcessingTheater(total=len(docs), gateway=gateway_status)
    timings: dict[str, float] = st.session_state.setdefault("doc_times", {})
    started_at: dict[str, float] = {}

    _STAGE_LABELS = {
        "classifying": "Classifying", "ocr": "OCR", "ai": "AI Extraction",
        "extraction": "Extraction", "validation": "Validation",
        "confidence": "Confidence", "sap": "SAP Readiness", "done": "Completed",
    }

    def _progress(done: float, count: int, doc: DocumentState, phase: str) -> None:
        if phase == "classifying":
            started_at[doc.doc_id] = time.perf_counter()
        elif phase == "done" and doc.doc_id in started_at:
            timings[doc.doc_id] = time.perf_counter() - started_at[doc.doc_id]
        config.ai_gateway.set_stage(_STAGE_LABELS.get(phase, phase.title()))
        config.ai_gateway.set_queue(max(count - int(done), 0))
        theater.update(done, count, doc, phase)

    classifier = None
    candidates = None
    if processor is None:
        classifier = build_classifier()
        candidates = [
            p for p in (production_processors_for_department(nav.department.key) or active_processors())
            if p.spec.engine != "tabular"
        ]

    config.ai_gateway.set_queue(len(docs))
    process_batch(
        docs,
        processor=processor,
        classifier=classifier,
        candidates=candidates,
        progress_cb=_progress,
    )
    theater.finish()
    config.ai_gateway.set_stage("Idle")
    config.ai_gateway.set_queue(0)

    for doc in docs:
        manager.add(doc)

    try:
        history.record_batch(docs, nav.mode, nav.department.name)
    except Exception:  # noqa: BLE001 - history is non-critical
        logger.exception("Failed to record batch history.")


# ----- Process view ------------------------------------------------------ #


def _can_process(spec, dev_mode: bool) -> bool:
    """True if a processor may run for the current user (production, or dev)."""
    if spec.status == PRODUCTION:
        return True
    return dev_mode and spec.status in (TESTING, DRAFT)


def _render_process_view(nav: Nav) -> None:
    """Render the document processing workspace for the selected mode."""
    # The Management department surfaces the executive dashboard rather than an
    # upload workspace (it owns no document processors of its own).
    if nav.department.key == "management":
        ui.render_breadcrumb(nav.department.name, "Executive Dashboard")
        _render_management_dashboard(nav)
        return

    handled_tabular = False
    if nav.mode == _MODE_MANUAL:
        ui.render_breadcrumb(nav.department.name, "Manual · select business process")
        handled_tabular = _render_manual_mode(nav)
    else:
        ui.render_breadcrumb(nav.department.name, "Auto Detect · AI picks the process")
        _render_auto_mode(nav)

    # Tabular processors render their own summary + download; skip the AI-only
    # register and per-document review sections for them.
    if not handled_tabular:
        _render_register_downloads(nav)
        _render_documents()


def _render_management_dashboard(nav: Nav) -> None:
    """Render the executive (management) dashboard.

    A business-facing operational overview: department + processor statistics,
    today's documents, average confidence, average processing time, estimated
    cost, gateway health, and the all-time success rate — visualized as glass
    KPI cards with confidence rings, a live AI Gateway card, department summary
    cards, and the informational processor marketplace. Read-only; it never
    exposes JSON or any sensitive value.
    """
    from datetime import datetime, timezone

    from utils.confidence import band, overall_confidence

    ui.section_heading("📊 Executive Dashboard")
    st.caption(
        "Live operational overview across the India Glycols Enterprise "
        "Document Intelligence Platform."
    )

    procs = all_processors()
    installed = active_processors()
    coming = [p for p in procs if p.spec.status == COMING_SOON]
    live_dept_keys = {p.spec.department_key for p in installed}

    cost_summary = cost.summary()
    totals = cost_summary["totals"]
    today_usage = cost_summary.get("today", {})

    batches = history.list_batches()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_docs = sum(
        int(b.get("total", 0))
        for b in batches
        if str(b.get("timestamp", "")).startswith(today)
    )
    hist_total = sum(int(b.get("total", 0)) for b in batches)
    hist_success = sum(int(b.get("success", 0)) for b in batches)
    success_rate = round(hist_success / hist_total * 100) if hist_total else 100

    manager = _manager()
    done = [d for d in manager.documents if d.status == "done" and d.confidence]
    confidences = [overall_confidence(d.confidence) for d in done]
    avg_conf = round(sum(confidences) / len(confidences)) if confidences else 0
    times = list(st.session_state.get("doc_times", {}).values())
    avg_time = f"{sum(times) / len(times):.1f}s" if times else "—"

    gw = config.ai_gateway.status()
    gw_healthy = bool(gw.get("healthy")) and config.ai_gateway.has_capacity()

    ui.glass_kpi_cards([
        {"label": "Departments", "value": f"{len(live_dept_keys)}/{len(DEPARTMENTS)}",
         "sub": "with live processors", "icon": "🏢"},
        {"label": "Processors", "value": f"{len(installed)}/{len(procs)}",
         "sub": "installed / registered", "icon": "🧩"},
        {"label": "Today's Documents", "value": str(today_docs),
         "sub": "processed today", "icon": "📄"},
        {"label": "Average Confidence", "value": f"{avg_conf}%" if confidences else "—",
         "sub": "this session",
         "ring": {"score": avg_conf, "band": band(avg_conf)} if confidences else None,
         "icon": "📈"},
        {"label": "Avg Processing Time", "value": avg_time,
         "sub": "per document", "icon": "⚡"},
        {"label": "Estimated Cost", "value": f"₹ {totals['cost_inr']:.2f}",
         "sub": "all-time", "icon": "₹"},
        {"label": "Success Rate", "value": f"{success_rate}%", "sub": "all batches",
         "ring": {"score": success_rate, "band": band(success_rate)}, "icon": "✅"},
        {"label": "Gateway Health", "value": "Healthy" if gw_healthy else "Offline",
         "sub": str(gw.get("provider") or "—").title(), "icon": "🛡️"},
        {"label": "Today's AI Cost", "value": f"₹ {today_usage.get('cost_inr', 0):.2f}",
         "sub": f"{today_usage.get('tokens', 0):,} tokens today", "icon": "₹"},
        {"label": "Retry Usage", "value": str(cost_summary.get("retry_count", 0)),
         "sub": "stronger-model retries", "icon": "↻"},
    ])

    ui.section_heading("🛡️ AI Gateway")
    pending = sum(1 for d in manager.documents if d.status == "pending")
    ui.render_gateway_status(gw, queue=pending, stage="Idle")

    ui.section_heading("🏢 Department Summary")
    ui.department_summary_cards([
        {
            "key": dept.key,
            "name": dept.name,
            "live": sum(1 for p in installed if p.spec.department_key == dept.key),
            "total": sum(1 for p in procs if p.spec.department_key == dept.key),
        }
        for dept in DEPARTMENTS
    ])

    ui.processor_marketplace(
        installed=[p.spec.business_process or p.spec.document_type for p in installed],
        coming_soon=sorted(
            {p.spec.business_process or p.spec.document_type for p in coming}
        ),
    )


def _render_manual_mode(nav: Nav) -> bool:
    """Manual mode: pick a business process via the catalog, then upload to it.

    Returns True when a deterministic (tabular) processor handled the upload, so
    the caller can skip the AI register / per-document review sections.
    """
    processes = business_processes_for_department(nav.department.key)
    if not processes:
        ui.coming_soon_hero(nav.department.name, "No processes configured yet")
        return False

    # Visible processes: business users see production + coming_soon; developers
    # additionally see testing/draft.
    visible = [
        p for p in processes
        if p.spec.status in (PRODUCTION, COMING_SOON) or nav.dev_mode
    ]
    if not visible:
        ui.coming_soon_hero(nav.department.name, "No processes available yet")
        return False

    # Selection state is kept per department so switching departments is sticky.
    sel_key = f"proc_select:{nav.department.key}"
    keys = [p.spec.use_case_key for p in visible]
    default_key = next(
        (p.spec.use_case_key for p in visible if p.spec.status == PRODUCTION),
        keys[0],
    )
    current = st.session_state.get(sel_key)
    if current not in keys:
        current = default_key
        st.session_state[sel_key] = current

    _render_process_catalog(nav, visible, current, sel_key)

    processor = next(p for p in visible if p.spec.use_case_key == current)

    if not _can_process(processor.spec, nav.dev_mode):
        ui.coming_soon_hero(
            nav.department.name,
            processor.spec.business_process or processor.spec.document_type,
        )
        return False

    spec = processor.spec
    ui.selected_process_bar(
        name=spec.business_process or spec.document_type,
        dept_name=spec.department_name or nav.department.name,
        dept_key=spec.department_key or nav.department.key,
        status=spec.status,
        engine=spec.engine,
    )

    # Deterministic Excel/CSV processors (e.g. RA Posting) have their own upload
    # + summary workspace and never touch the AI pipeline.
    if processor.spec.engine == "tabular":
        _render_tabular_processor(nav, processor)
        return True

    _render_uploader_and_process(nav, processor)
    return False


# ----- Process catalog (search / filter / paging — scales to 100+) ------ #

#: Cards shown before the catalog collapses behind "Show all …".
_CATALOG_PAGE = 9
#: Display order + toolbar labels per lifecycle status.
_STATUS_LABELS = {
    PRODUCTION: "Live",
    TESTING: "Testing",
    DRAFT: "Draft",
    COMING_SOON: "Coming Soon",
}
_STATUS_RANK = {PRODUCTION: 0, TESTING: 1, DRAFT: 2, COMING_SOON: 3}


def _catalog_filter(
    processors: list[BaseProcessor], query: str, status_label: str
) -> list[BaseProcessor]:
    """Filter + rank the catalog: text search, status filter, live first."""
    query = query.strip().lower()
    wanted_status = next(
        (s for s, lbl in _STATUS_LABELS.items() if lbl == status_label), None
    )

    def matches(spec) -> bool:
        if wanted_status and spec.status != wanted_status:
            return False
        if not query:
            return True
        haystack = " ".join(
            [
                spec.business_process or "",
                spec.document_type or "",
                spec.ai_description or "",
                " ".join(spec.keywords),
            ]
        ).lower()
        return all(term in haystack for term in query.split())

    filtered = [p for p in processors if matches(p.spec)]
    filtered.sort(
        key=lambda p: (
            _STATUS_RANK.get(p.spec.status, 9),
            (p.spec.business_process or p.spec.document_type).lower(),
        )
    )
    return filtered


def _render_process_catalog(
    nav: Nav,
    processors: list[BaseProcessor],
    current_key: str,
    sel_key: str,
) -> None:
    """Render the searchable, filterable business-process catalog.

    Built to stay pleasant at 100+ processes per department: a keyword search
    (name, document type, keywords, AI description), lifecycle filter pills,
    live-first ranking, and a nine-card page with "Show all" expansion. The
    active selection is always visible in the selected-process bar rendered by
    the caller, even when filtered out of the grid.
    """
    ui.section_heading("🗂️ Select a Business Process")

    col_search, col_filter = st.columns([3, 2], gap="medium")
    with col_search:
        query = st.text_input(
            "Search processes",
            key=f"cat_query:{nav.department.key}",
            placeholder=f"Search {len(processors)} processes — name, keyword, description…",
            label_visibility="collapsed",
        )
    statuses_present = {p.spec.status for p in processors}
    options = ["All"] + [
        lbl for s, lbl in _STATUS_LABELS.items() if s in statuses_present
    ]
    with col_filter:
        status_label = (
            st.pills(
                "Status",
                options,
                default="All",
                key=f"cat_status:{nav.department.key}",
                label_visibility="collapsed",
            )
            or "All"
        )

    filtered = _catalog_filter(processors, query, status_label)
    live = sum(1 for p in processors if p.spec.status == PRODUCTION)

    if not filtered:
        ui.catalog_meta(0, len(processors), live, query)
        ui.catalog_empty(query or status_label)
        return

    all_key = f"cat_all:{nav.department.key}"
    show_all = bool(st.session_state.get(all_key, False))
    subset = filtered if show_all or len(filtered) <= _CATALOG_PAGE else filtered[:_CATALOG_PAGE]
    ui.catalog_meta(len(subset), len(processors), live, query)

    per_row = 3
    for start in range(0, len(subset), per_row):
        row = subset[start : start + per_row]
        cols = st.columns(per_row)
        for col, proc in zip(cols, row):
            spec = proc.spec
            selected = spec.use_case_key == current_key
            with col:
                st.markdown(
                    ui.processor_card_html(
                        name=spec.business_process or spec.document_type,
                        dept_name=spec.department_name or nav.department.name,
                        dept_key=spec.department_key or nav.department.key,
                        status=spec.status,
                        accuracy=spec.accuracy,
                        selected=selected,
                    ),
                    unsafe_allow_html=True,
                )
                if st.button(
                    "✓ Selected" if selected else "Select",
                    key=f"pick:{nav.department.key}:{spec.use_case_key}",
                    use_container_width=True,
                    type="primary" if selected else "secondary",
                ):
                    st.session_state[sel_key] = spec.use_case_key
                    st.rerun()

    if len(filtered) > _CATALOG_PAGE:
        label = (
            "Show fewer processes"
            if show_all
            else f"Show all {len(filtered)} processes"
        )
        if st.button(label, key=f"cat_more:{nav.department.key}", use_container_width=True):
            st.session_state[all_key] = not show_all
            st.rerun()


def _render_auto_mode(nav: Nav) -> None:
    """Auto Detect mode: upload, then classify among production processors."""
    candidates = [
        p for p in production_processors_for_department(nav.department.key)
        if p.spec.engine != "tabular"
    ]
    if not candidates:
        st.info(
            f"No live processors in **{nav.department.name}** yet. Switch "
            f"departments or use Manual mode. (Available live processes elsewhere.)"
        )
        if not active_processors():
            return
    names = ", ".join(p.spec.business_process or p.spec.document_type for p in candidates) or "—"
    st.caption(f"📑 Auto-detecting among: {names}")
    _render_uploader_and_process(nav, processor=None)


# ----- Tabular (deterministic Excel/CSV) workspace ---------------------- #


def _render_tabular_processor(nav: Nav, processor: BaseProcessor) -> None:
    """Deterministic Excel/CSV workspace (e.g. RA Posting) — no AI pipeline.

    Uploads are parsed by the processor's own ``parser.py`` into a merged
    customer summary that is previewed and offered as an Excel download.
    """
    spec = processor.spec
    title = spec.business_process or spec.document_type
    ui.section_heading(f"📥 {title}")
    st.caption(
        "Upload SBI or IDBI bank statements (Excel or CSV). Only credit (CR) "
        "entries are kept and merged into a customer-wise summary — grouped A–Z "
        "with per-customer subtotals and a grand total."
    )

    result_key = f"tabular_result:{spec.use_case_key}"
    files = st.file_uploader(
        f"Upload statements for {title}",
        type=["xlsx", "xls", "xlsb", "csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key=f"tabular_upload:{spec.use_case_key}",
    )

    if files and st.button("⚡ Generate Summary", type="primary", use_container_width=True):
        payload = [(f.name, f.getvalue()) for f in files]
        with ui.loader_3d(
            "Parsing statements…",
            "Merging credit entries into the customer-wise summary",
        ):
            try:
                st.session_state[result_key] = processor.run_tabular(payload)
            except Exception as exc:  # noqa: BLE001 - surface a clean message
                logger.exception("Tabular processing failed for %s", spec.use_case_key)
                st.error(f"Could not build the summary: {exc}")
                st.session_state.pop(result_key, None)

    result = st.session_state.get(result_key)
    if result:
        _render_tabular_result(spec, result)


def _render_tabular_result(spec, result: dict) -> None:
    """Render stats, warnings, a preview table, and the Excel download."""
    stats = result.get("stats", {})
    cols = st.columns(4)
    cols[0].metric("Files", stats.get("files", 0))
    cols[1].metric("Credit entries", stats.get("credit_entries", 0))
    cols[2].metric("Customers", stats.get("customers", 0))
    cols[3].metric("Total (₹)", f"{stats.get('total_amount', 0):,.2f}")

    banks = ", ".join(stats.get("banks", [])) or "—"
    naming = "AI-cleaned names" if stats.get("ai_used") else "rule-based names"
    st.caption(f"Detected bank(s): **{banks}** · Customer names: **{naming}**")

    for warning in result.get("warnings", []):
        st.warning(warning)

    rows = result.get("rows", [])
    if not rows:
        st.info("No credit (CR) entries were found in the uploaded file(s).")
        return

    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download Customer Summary (Excel)",
        data=result.get("excel_bytes", b""),
        file_name=f"{spec.json_suffix or spec.use_case_key}_summary.xlsx",
        mime=_EXCEL_MIME,
        type="primary",
        use_container_width=True,
    )


def _render_uploader_and_process(nav: Nav, processor: BaseProcessor | None) -> None:
    """Render the upload hint, uploader, cost predictor, duplicate check, process."""
    target = processor.spec.business_process if processor else f"{nav.department.name} documents"
    _render_upload_hint(target if processor else None)
    uploaded_files = st.file_uploader(
        f"Upload documents for {target} (PDF or image)",
        type=_SUPPORTED_TYPES,
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if not uploaded_files:
        return

    # Cost predictor — set expectations before any AI call.
    _render_cost_prediction(uploaded_files)

    # Duplicate detection — never reprocess a known document silently.
    dupes = _detect_duplicates(uploaded_files)
    if dupes:
        _render_duplicate_cards(dupes)
        col_go, col_cancel = st.columns(2)
        with col_go:
            proceed = st.button(
                "⚠️ Continue Anyway", type="primary", use_container_width=True
            )
        with col_cancel:
            # A plain no-op button: not processing IS the cancel. The rest of
            # the page (registers, processed documents) keeps rendering.
            if st.button("Cancel", use_container_width=True):
                st.info(
                    "Processing cancelled. Remove the file(s) above or continue anyway."
                )
        if proceed:
            _run_processing(nav, _build_doc_states(uploaded_files), processor)
        return

    if st.button("⚡ Process Documents", type="primary"):
        _run_processing(nav, _build_doc_states(uploaded_files), processor)


@st.cache_data(show_spinner=False, max_entries=256)
def _page_count(file_bytes: bytes, mime_type: str) -> int:
    """Cheaply count pages for the cost predictor (PDF page count; else 1).

    Cached by content so re-runs (every widget interaction re-executes the
    script) never re-open the same PDF just to count its pages.
    """
    if mime_type == "application/pdf":
        try:
            import fitz  # PyMuPDF

            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                return max(doc.page_count, 1)
        except Exception:  # noqa: BLE001 - prediction is best-effort
            return 1
    return 1


def _render_cost_prediction(uploaded_files: list) -> None:
    """Show the predicted tokens + ₹ cost before processing (no AI call)."""
    total_pages = 0
    for uploaded in uploaded_files:
        try:
            mime = guess_mime_type(uploaded.name)
        except ValueError:
            continue
        total_pages += _page_count(uploaded.getvalue(), mime)
    prediction = cost.predict(total_pages, settings.default_model)
    ui.kpi_cards([
        ("Documents", str(len(uploaded_files)), f"~{total_pages} page(s)"),
        ("Est. tokens", f"{prediction['expected_tokens']:,}", "predicted"),
        ("Est. cost", f"₹ {prediction['est_cost_inr']:.2f}", prediction["model"]),
    ])


def _detect_duplicates(uploaded_files: list) -> list[tuple[str, dict]]:
    """Return (filename, record) for uploads whose fingerprint was seen before."""
    found: list[tuple[str, dict]] = []
    for uploaded in uploaded_files:
        record = duplicates.check(duplicates.fingerprint(uploaded.getvalue()))
        if record:
            found.append((uploaded.name, record))
    return found


def _render_duplicate_cards(dupes: list[tuple[str, dict]]) -> None:
    """Render the 'Already Processed' warning for duplicate uploads."""
    rows = "".join(
        f'<div class="igl-dup-meta"><b>{name}</b> — processed '
        f'{rec.get("date", "?")} · {rec.get("processor", "?")} · '
        f'{rec.get("department", "?")}</div>'
        for name, rec in dupes
    )
    st.markdown(
        f'<div class="igl-dup"><div class="igl-dup-title">'
        f"⚠️ {len(dupes)} document(s) already processed</div>{rows}</div>",
        unsafe_allow_html=True,
    )


# ----- Register downloads (primary business export) --------------------- #


def _render_register_downloads(nav: Nav) -> None:
    """Render the consolidated one-row-per-PDF Excel register download(s)."""
    manager = _manager()
    processed = manager.processed
    if not processed:
        return

    ui.section_heading("📊 Excel Register")
    st.caption("One row per document. Each document type produces its own workbook.")
    registers = consolidated_excel.build_registers(processed)

    if len(registers) == 1:
        name, data = next(iter(registers.items()))
        st.download_button(
            f"⬇️ Download Register · {name}",
            data=data,
            file_name=name,
            mime=_EXCEL_MIME,
            type="primary",
            use_container_width=True,
        )
    else:
        columns = st.columns(min(len(registers), 3))
        for index, (name, data) in enumerate(registers.items()):
            with columns[index % len(columns)]:
                st.download_button(
                    f"⬇️ {name}",
                    data=data,
                    file_name=name,
                    mime=_EXCEL_MIME,
                    use_container_width=True,
                    key=f"reg_{name}",
                )
        st.download_button(
            "⬇️ Download all registers (ZIP)",
            data=consolidated_excel.registers_zip(processed),
            file_name="registers.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )

    if nav.dev_mode:
        with st.expander("Developer exports (JSON / Excel ZIP)"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.download_button("All JSON (ZIP)", data=manager.all_json_zip(),
                                   file_name="all_json.zip", mime="application/zip", use_container_width=True)
            with c2:
                st.download_button("All Excel (ZIP)", data=manager.all_excel_zip(),
                                   file_name="all_excel.zip", mime="application/zip", use_container_width=True)
            with c3:
                st.download_button("JSON + Excel (ZIP)", data=manager.full_zip(),
                                   file_name="all_documents.zip", mime="application/zip", use_container_width=True)


# ----- Documents (per-document review via the generic engine) ----------- #


def _doc_seconds(doc_id: str) -> float | None:
    """Return the recorded processing time (seconds) for a document, if any."""
    return st.session_state.get("doc_times", {}).get(doc_id)


#: Above this many documents, tabs overflow — switch to a picker.
_MAX_DOC_TABS = 8


def _render_documents() -> None:
    """Render the per-document review area, driven by the generic engine.

    Up to :data:`_MAX_DOC_TABS` documents render as tabs; larger batches switch
    to a status summary + document picker so the navigation stays usable for
    batches of any size.
    """
    manager = _manager()
    docs = manager.documents
    if not docs:
        ui.onboarding_hero()
        return

    ui.section_heading("📄 Documents")

    if len(docs) <= _MAX_DOC_TABS:
        labels = [f"{ui.status_icon(doc.status)} {doc.filename}" for doc in docs]
        tabs = st.tabs(labels)
        for tab, doc in zip(tabs, docs):
            with tab:
                _render_document_body(doc)
        return

    # Large batch: status KPIs + a picker instead of an overflowing tab strip.
    done = sum(1 for d in docs if d.status == "done")
    errors = sum(1 for d in docs if d.status in ("error", "unsupported"))
    ui.kpi_cards([
        ("Documents", str(len(docs)), "in this batch"),
        ("Processed", str(done), "ready for review"),
        ("Attention", str(errors), "failed / unsupported"),
    ])
    choice = st.selectbox(
        "Select a document to review",
        options=range(len(docs)),
        format_func=lambda i: (
            f"{ui.status_icon(docs[i].status)} {docs[i].filename} · #{i + 1}"
        ),
        key="doc_picker",
    )
    _render_document_body(docs[choice])


def _render_document_body(doc: DocumentState) -> None:
    """Render one document's header + workspace/error content."""
    _render_document_header(doc)
    if doc.status == "unsupported":
        st.error("Unsupported document type for this department.")
    elif doc.status == "error":
        st.error(f"Extraction failed: {doc.error}")
    elif doc.status == "done":
        render_document_workspace(doc)
    else:
        st.info("This document has not been processed yet.")


def _render_document_header(doc: DocumentState) -> None:
    """Render the premium classification summary card for a document."""
    method = {"ai": "AI", "manual": "Manual", "keyword": "Keywords"}.get(
        doc.classification_method, doc.classification_method
    )
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
        f'<div class="igl-doc-meta">Routed via {method}{timing}</div>'
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


# ----- History view ------------------------------------------------------ #


def _render_history_view() -> None:
    """Render the processing history with per-batch register re-downloads."""
    ui.section_heading("🕓 Processing History")
    batches = history.list_batches()
    if not batches:
        st.info("No processed batches yet. Process documents to build history.")
        return

    for batch in batches:
        title = (
            f"{batch.get('id')} · {batch.get('department', '')} · {batch.get('mode', '')} · "
            f"{batch.get('success', 0)}/{batch.get('total', 0)} ok"
        )
        with st.expander(title):
            by_type = batch.get("by_type", {})
            ui.kpi_cards([
                ("Documents", str(batch.get("total", 0)), "in this batch"),
                ("Succeeded", str(batch.get("success", 0)), "extracted"),
                ("With warnings", str(batch.get("warnings", 0)), "need review"),
                ("Errors", str(batch.get("errors", 0)), "failed"),
            ])
            if by_type:
                st.caption("Types: " + ", ".join(f"{k} ({v})" for k, v in by_type.items()))
            for name in batch.get("files", []):
                data = history.load_file(batch["id"], name)
                if data:
                    st.download_button(
                        f"⬇️ {name}",
                        data=data,
                        file_name=name,
                        mime=_EXCEL_MIME,
                        key=f"hist_{batch['id']}_{name}",
                    )


# ----- Cost & health view ------------------------------------------------ #


def _render_cost_health_view() -> None:
    """Render the cost dashboard and the processor health dashboard."""
    ui.section_heading("💸 Cost Dashboard")
    summary = cost.summary()
    totals = summary["totals"]
    today = summary.get("today", {})
    ui.kpi_cards([
        ("Documents (AI)", str(totals["docs"]), "all-time extractions"),
        ("Tokens", f"{totals['tokens']:,}", "total"),
        ("Estimated cost", f"₹ {totals['cost_inr']:.2f}", "all-time"),
        ("Avg cost / doc", f"₹ {totals.get('avg_cost_inr', 0):.3f}", f"~{totals.get('avg_tokens', 0):,} tokens"),
        ("Avg time / doc", f"{totals.get('avg_proc_ms', 0) / 1000:.1f}s", "processing"),
        ("Retry usage", str(summary.get("retry_count", 0)), "stronger-model retries"),
        ("Today", f"₹ {today.get('cost_inr', 0):.2f}", f"{today.get('docs', 0)} docs · {today.get('tokens', 0):,} tokens"),
    ])
    if summary.get("by_model"):
        st.caption("By model (DEFAULT vs RETRY)")
        st.dataframe(
            [{"Model": k, **v} for k, v in summary["by_model"].items()],
            use_container_width=True, hide_index=True,
        )
    if summary["by_processor"]:
        st.caption("By processor")
        _cost_breakdown_chart(summary["by_processor"], "Processor")
        st.dataframe(
            [{"Processor": k, **v} for k, v in summary["by_processor"].items()],
            use_container_width=True, hide_index=True,
        )
    if summary["by_department"]:
        st.caption("By department")
        _cost_breakdown_chart(summary["by_department"], "Department")
        st.dataframe(
            [{"Department": k, **v} for k, v in summary["by_department"].items()],
            use_container_width=True, hide_index=True,
        )
    if summary["by_month"]:
        st.caption("By month")
        _cost_breakdown_chart(summary["by_month"], "Month")
        st.dataframe(
            [{"Month": k, **v} for k, v in summary["by_month"].items()],
            use_container_width=True, hide_index=True,
        )

    ui.section_heading("❤️ Processor Health")
    _render_processor_health(summary["by_processor"])


def _cost_breakdown_chart(breakdown: dict, label: str) -> None:
    """Render a compact cost bar chart for one summary breakdown (₹ per key)."""
    import pandas as pd

    rows = [
        {label: key, "Cost (₹)": float(usage.get("cost_inr", 0) or 0)}
        for key, usage in breakdown.items()
    ]
    frame = pd.DataFrame(rows)
    if frame.empty or not frame["Cost (₹)"].sum():
        return
    st.bar_chart(frame, x=label, y="Cost (₹)", height=220, color="#3B82F6")


def _render_processor_health(by_processor: dict) -> None:
    """Render per-processor health from this session + recorded usage."""
    manager = _manager()
    rows = []
    for processor in active_processors():
        key = processor.spec.use_case_key
        docs = [d for d in manager.documents if d.processor is processor]
        done = [d for d in docs if d.status == "done"]
        success = (len(done) / len(docs) * 100) if docs else 100.0
        from utils.confidence import overall_confidence

        confidences = [overall_confidence(d.confidence) for d in done if d.confidence]
        avg_conf = (sum(confidences) / len(confidences)) if confidences else 0
        usage = by_processor.get(key, {})
        rows.append({
            "Processor": processor.spec.business_process or processor.spec.document_type,
            "Status": processor.spec.status,
            "Session docs": len(docs),
            "Success %": round(success, 1),
            "Avg confidence": round(avg_conf, 1),
            "Total tokens": usage.get("tokens", 0),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


# ----- Shell ------------------------------------------------------------- #


def _render_upload_hint(process_name: str | None = None) -> None:
    """Render the premium, centered drag-and-drop hint above the uploader.

    When a process is selected the chips describe what THIS process accepts,
    instead of a hardcoded sample of other departments' document types.
    """
    if process_name:
        types = [f"{process_name} PDFs", "Scanned Copies", "Photos", "Multi-page", "Handwriting"]
    else:
        types = ["PDFs", "Scanned Copies", "Photos", "Multi-page", "Handwriting"]
    chips = "".join(f"<span>{t}</span>" for t in types)
    st.markdown(
        f'<div class="igl-upload-hint">'
        f'<div class="glyph">📄</div>'
        f'<div class="ttl">Drop Documents Here</div>'
        f'<div class="types">{chips}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    """Run the India Glycols Enterprise Document Intelligence Platform."""
    st.set_page_config(
        page_title="India Glycols · Document Intelligence Platform",
        page_icon="🧪",
        layout="wide",
    )
    ui.inject_theme()
    ui.render_header(
        settings.assets_dir,
        live_processors=len(active_processors()),
        total_processes=len(all_processors()),
    )

    nav = _render_sidebar()

    if not has_ai_key():
        st.error(
            f"No API key is configured for the '{settings.ai_provider}' provider. "
            "Set AI_PROVIDER and AI_API_KEY (and DEFAULT_MODEL / RETRY_MODEL) in "
            "the .env file and restart the application."
        )

    if nav.view == "process":
        _render_process_view(nav)
    elif nav.view == "history":
        _render_history_view()
    elif nav.view == "cost":
        _render_cost_health_view()
    elif nav.view == "admin":
        admin.render_admin()


if __name__ == "__main__":
    main()
