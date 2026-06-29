"""Admin panel — onboard and manage document processors without writing code.

This is what turns the application into a *platform*: an operator can create a
new processor by filling a short form and uploading its prompt(s), schema,
Excel template and samples. The panel writes a ``manifest.json`` plus the files
into ``processors/<key>/`` and triggers a fresh discovery pass — the new
processor then appears in navigation immediately.

Processor lifecycle is managed here too: a new processor starts as **draft**,
can be promoted to **testing** and then **production** (only production is
visible to business users). Draft processors can be deleted.

All file writes are confined to the ``processors/`` tree; uploads are saved with
sanitized names.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

import streamlit as st

import ui
from departments import DEPARTMENTS
from processors.bootstrap import refresh_processors
from processors.registry import all_processors
from processors.spec import COMING_SOON, DRAFT, PRODUCTION, TESTING

logger = logging.getLogger(__name__)

_PROCESSORS_DIR = Path(__file__).resolve().parent / "processors"
_PROMOTE_NEXT = {DRAFT: TESTING, TESTING: PRODUCTION}
_DEMOTE_NEXT = {PRODUCTION: TESTING, TESTING: DRAFT}


def _slug(value: str) -> str:
    """Normalize a processor key to a safe snake_case slug."""
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return slug


def _safe_name(name: str) -> str:
    """Sanitize an uploaded filename (strip any path components)."""
    return Path(name).name


def _derive_from_schema(schema: dict[str, Any]) -> tuple[list, list, dict | None]:
    """Derive review sections, register columns, and line items from a schema.

    Top-level dict blocks become sections of their scalar children; the first
    list-of-objects becomes the line-item table. This gives an admin-created
    processor a working review UI and register from just its schema.
    """
    skip = {"metadata", "remarks", "additional_information", "missing_fields",
            "warnings", "errors", "validation"}
    sections: list[dict[str, Any]] = []
    export_columns: list[dict[str, Any]] = []
    line_items: dict[str, Any] | None = None

    for top_key, value in schema.items():
        if top_key in skip:
            continue
        if isinstance(value, dict):
            fields = []
            for key, val in value.items():
                if isinstance(val, (dict, list)):
                    continue
                path = f"{top_key}.{key}"
                label = key.replace("_", " ").title()
                kind = "number" if isinstance(val, (int, float)) and not isinstance(val, bool) else "text"
                fields.append({"path": path, "label": label, "kind": kind})
                export_columns.append({"header": label, "path": path})
            if fields:
                sections.append({"title": top_key.replace("_", " ").title(), "fields": fields})
        elif isinstance(value, list) and value and isinstance(value[0], dict) and line_items is None:
            columns = [
                {"key": k, "label": k.replace("_", " ").title(),
                 "kind": "number" if isinstance(v, (int, float)) and not isinstance(v, bool) else "text"}
                for k, v in value[0].items()
            ]
            line_items = {"path": top_key, "columns": columns}
    return sections, export_columns, line_items


def _set_status(processor_key: str, status: str) -> None:
    """Update a processor's lifecycle status in its manifest and re-discover."""
    manifest_path = _PROCESSORS_DIR / processor_key / "manifest.json"
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = status
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    refresh_processors()
    logger.info("Processor '%s' set to %s.", processor_key, status)


def _delete_processor(processor_key: str) -> None:
    """Delete a draft processor's folder and re-discover."""
    folder = _PROCESSORS_DIR / processor_key
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
        refresh_processors()
        logger.info("Deleted processor '%s'.", processor_key)


def render_admin() -> None:
    """Render the full admin panel (registry table + create/update form)."""
    ui.section_heading("🛠️ Admin · Processor Management")
    st.caption(
        "Create and manage document processors without code. New processors "
        "start as **Draft** and become visible to business users only at "
        "**Production**."
    )

    _render_registry_table()
    st.divider()
    _render_create_form()


def _render_registry_table() -> None:
    """List every registered processor with lifecycle controls."""
    ui.section_heading("Registered Processors")
    processors = sorted(
        all_processors(),
        key=lambda p: (p.spec.department_order, p.spec.business_process.lower()),
    )
    for processor in processors:
        spec = processor.spec
        cols = st.columns([3, 2, 2, 3])
        with cols[0]:
            st.markdown(
                f"**{spec.business_process or spec.document_type}**  \n"
                f"<span style='color:rgba(255,255,255,0.5);font-size:12px;'>"
                f"{spec.department_name} · `{spec.use_case_key}`</span>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(ui.lifecycle_chip(spec.status), unsafe_allow_html=True)
        with cols[2]:
            promote = _PROMOTE_NEXT.get(spec.status)
            if promote and st.button(f"Promote → {promote}", key=f"promote_{spec.use_case_key}"):
                _set_status(spec.use_case_key, promote)
                st.rerun()
            demote = _DEMOTE_NEXT.get(spec.status)
            if demote and st.button(f"Demote → {demote}", key=f"demote_{spec.use_case_key}"):
                _set_status(spec.use_case_key, demote)
                st.rerun()
        with cols[3]:
            if spec.status in (DRAFT, COMING_SOON):
                if st.button("🗑️ Delete", key=f"delete_{spec.use_case_key}"):
                    _delete_processor(spec.use_case_key)
                    st.rerun()


def _render_create_form() -> None:
    """Render the create/update processor form with file uploads."""
    ui.section_heading("Create / Update Processor")
    with st.form("admin_create_processor", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            key_input = st.text_input("Processor key (snake_case)", placeholder="e.g. credit_note")
            document_type = st.text_input("Document type (label)", placeholder="Credit Note")
            business_process = st.text_input("Business process", placeholder="Credit Note")
        with c2:
            dept_index = st.selectbox(
                "Department",
                options=range(len(DEPARTMENTS)),
                format_func=lambda i: f"{DEPARTMENTS[i].icon} {DEPARTMENTS[i].name}",
            )
            status = st.selectbox("Lifecycle status", [DRAFT, TESTING, PRODUCTION], index=0)
            keywords = st.text_input("Keywords (comma-separated)", placeholder="credit note, gst, refund")

        ai_description = st.text_area("AI description (used by the classifier)", height=70)

        st.markdown("**Assets** — upload at least a schema + extraction prompt for a working processor.")
        u1, u2 = st.columns(2)
        with u1:
            system_prompt = st.file_uploader("System prompt (.txt)", type=["txt"], key="adm_sys")
            extraction_prompt = st.file_uploader("Extraction prompt (.txt)", type=["txt"], key="adm_ext")
        with u2:
            schema_file = st.file_uploader("Schema (schema.json)", type=["json"], key="adm_schema")
            template_file = st.file_uploader("Excel template (.xlsx)", type=["xlsx"], key="adm_tpl")
        samples = st.file_uploader(
            "Sample documents (optional, multiple)", accept_multiple_files=True, key="adm_samples"
        )

        submitted = st.form_submit_button("💾 Save processor", type="primary")

    if submitted:
        _handle_create(
            key_input, document_type, business_process, DEPARTMENTS[dept_index],
            status, keywords, ai_description,
            system_prompt, extraction_prompt, schema_file, template_file, samples,
        )


def _handle_create(
    key_input: str, document_type: str, business_process: str, department: Any,
    status: str, keywords: str, ai_description: str,
    system_prompt: Any, extraction_prompt: Any, schema_file: Any,
    template_file: Any, samples: Any,
) -> None:
    """Validate inputs, write the processor folder + manifest, and re-discover."""
    key = _slug(key_input)
    if not key:
        st.error("A valid processor key is required.")
        return
    if not document_type.strip():
        st.error("Document type is required.")
        return

    folder = _PROCESSORS_DIR / key
    (folder / "prompts" / "v1").mkdir(parents=True, exist_ok=True)
    (folder / "schema").mkdir(parents=True, exist_ok=True)
    (folder / "templates").mkdir(parents=True, exist_ok=True)
    (folder / "samples" / "raw").mkdir(parents=True, exist_ok=True)

    sections: list = []
    export: dict[str, Any] | None = None
    line_items: dict | None = None

    if schema_file is not None:
        try:
            schema = json.loads(schema_file.getvalue().decode("utf-8"))
            (folder / "schema" / "schema.json").write_text(
                json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            sections, export_columns, line_items = _derive_from_schema(schema)
            if export_columns:
                export = {"sheet": f"{business_process or document_type} Register",
                          "header_row": 1, "start_row": 2, "columns": export_columns}
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not parse schema JSON: {exc}")
            return

    if system_prompt is not None:
        (folder / "prompts" / "v1" / "system_prompt.txt").write_bytes(system_prompt.getvalue())
    if extraction_prompt is not None:
        (folder / "prompts" / "v1" / "extraction_prompt.txt").write_bytes(extraction_prompt.getvalue())
    if template_file is not None:
        tpl_name = _safe_name(template_file.name)
        (folder / "templates" / tpl_name).write_bytes(template_file.getvalue())
        if export is not None:
            export["template"] = f"templates/{tpl_name}"
    for sample in samples or []:
        (folder / "samples" / "raw" / _safe_name(sample.name)).write_bytes(sample.getvalue())

    manifest: dict[str, Any] = {
        "manifest_version": "1.0",
        "processor_version": "1.0",
        "schema_version": "1.0",
        "prompt_version": "v1",
        "key": key,
        "document_type": document_type.strip(),
        "business_process": (business_process or document_type).strip(),
        "status": status,
        "json_suffix": key,
        "department": {
            "key": department.key, "name": department.name,
            "icon": department.icon, "order": department.order,
        },
        "keywords": [k.strip().lower() for k in keywords.split(",") if k.strip()],
        "ai_description": ai_description.strip(),
        "sections": sections,
    }
    if line_items:
        manifest["line_items"] = line_items
    if export:
        manifest["export"] = export

    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    count = refresh_processors()
    logger.info("Admin saved processor '%s' (%d total).", key, count)
    st.success(
        f"Processor '{key}' saved as **{status}**. It is now discovered "
        f"({count} processors total)."
    )
    st.rerun()
