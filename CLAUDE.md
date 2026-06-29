# India Glycols — Enterprise Document Intelligence Platform

## Project Goal

An AI-powered Intelligent Document Processing (IDP) platform that converts
business documents from any vendor or format into standardized, ERP-ready
structured data and Excel registers.

Built for **India Glycols Limited** across multiple departments. The platform is
a **plugin system**: each document type is an independent, self-contained
processor folder discovered automatically from the filesystem. It is designed to
scale to hundreds of processors with **no architectural changes** — adding a
processor means adding a folder (or using the Admin panel).

Long-term goal: SAP integration.

## Current Status — Version 2.0

Live (production) processors:

- **Store → IGP** (Inward Gate Pass)
- **Marketing → Sales Order** (the migrated Purchase Order engine; key remains
  `purchase_order` internally, business label is "Sales Order")
- **Export → Shipping Bill**

Every other business process across the 11 departments is registered as
**coming soon** and renders a placeholder until built.

Platform capabilities (work automatically for every processor):

1. **Two modes** — **Manual** (Department → Business Process → upload; highest
   accuracy, the default) and **Auto Detect** (Department → upload → the AI picks
   the process).
2. Multi-document upload (PDF / image), each processed independently.
3. **Manifest-driven auto-discovery** — processors are discovered from
   `processors/<key>/manifest.json`; no hardcoded registration or routing.
4. **OCR preprocessing** — auto-orient, deskew, denoise, contrast (scanned PDFs
   are rasterized to enhanced page images; digital PDFs pass through).
5. AI extraction via Google Gemini using per-processor prompts + schema, with
   **multi-page** handling (all pages = one logical document) and **handwriting**
   preference.
6. **Validation → Auto-Fix → Export** — deterministic auto-fix (date/number
   normalization, etc.) reports each correction with a confidence score before
   validation; the reviewer resolves only what remains.
7. **Field-level + overall confidence** (green 95–100, yellow 75–94, red < 75).
8. **Editable review** — every field/line item is editable; edits update the
   standardized JSON live (re-export needs no AI).
9. **Excel registers** — ONE workbook per document type, **one row per uploaded
   PDF**, styled to match the uploaded business template (header styling, fonts,
   borders, widths, merged cells preserved). Per-document Excel is also kept.
10. **Extraction cache** — repeat uploads reuse the cached result and skip Gemini.
11. **Operational dashboards (Developer Mode)** — Processing History (with
    register re-download), Audit Trail (AI value → user value), Cost (tokens →
    ₹ estimate per processor/department/month), and Processor Health.
12. **Admin panel** — onboard a processor by uploading its prompt/schema/template/
    samples; lifecycle **draft → testing → production**.
13. **AI Gateway** — multiple API keys + multiple models with automatic rotation,
    model fallback, and graceful failover (unchanged from V1).

## Technology

- Python 3.11+, Streamlit
- Google Gemini API (`google-genai` SDK)
- OpenPyXL (Excel registers + per-doc workbooks), Pandas (editable tables)
- PyMuPDF (preview + scanned-PDF rasterization + text probe)
- Pillow (+ optional OpenCV `opencv-python-headless` for deskew/denoise)
- python-dotenv

## Architecture

```text
Mode: Manual (Department → Business Process)   |   Auto Detect (Department)
        |
        v
Upload Document(s)
        |
        v
OCR Preprocess  ──>  orient / deskew / denoise / enhance (scanned)
        |
        v
Route  ──>  Manual: assign chosen processor   |   Auto: classify (production only)
        |
        v
AI Gateway → Gemini Extraction  ──>  business data + per-field confidence
        |
        v
Normalize to Schema → Auto-Fix → Validate
        |
        v
Generic Engine  ──>  overall + field confidence, editing, preview, audit
        |
        v
Export  ──>  per-type Excel Register (1 row / PDF) + per-document Excel
        |
        v
SAP Integration (Future)
```

### Plugin model (manifest-driven)

A processor is a **folder** `processors/<key>/` described by a `manifest.json`
(metadata, lifecycle status, classification keywords/description, review
sections, line-item columns, and the register export mapping). One generic
`FolderProcessor` turns any such folder into a live processor; optional
`validator.py` / `exporter.py` in the folder override the generic behaviour.

Adding a new document type requires only:

1. Create `processors/<key>/` with a `manifest.json`.
2. Add `schema/schema.json` and `prompts/v1/{system,extraction}_prompt.txt`.
3. (Optional) Add `validator.py` (`validate` / `auto_fix`) and/or `exporter.py`.
4. (Optional) Add a styled `templates/…` workbook and reference it in the manifest.

No existing processor, the registry, the engine, or `app.py` is modified — the
processor is discovered on the next run. The **Admin panel** does all of this
from the UI.

## Folder & Module Responsibilities

### Application shell / engine
- `app.py`: Orchestration shell — mode toggle, department/business-process
  navigation, upload, processing queue, per-type register downloads, document
  tabs, and the Developer-Mode History / Cost & Health / Admin views.
- `engine.py`: Generic engine — overall + field confidence, auto-fix notes,
  editable fields/line items, preview, validation, audit, per-document export.
- `processing.py`: Per-document orchestration (preprocess → cache → classify or
  assign → extract → auto-fix → normalize → validate). The only place Gemini is
  called. `process_batch(progress_cb)` is UI-decoupled (background-ready).
- `classifier.py`: Auto-Detect classifier (AI primary, keyword fallback), driven
  by processor metadata.
- `preprocess.py`: OCR preprocessing (Pillow baseline + optional OpenCV).
- `cache.py`: Extraction cache (sha1 + processor + prompt version).
- `cost.py`: Token capture + ₹ estimate + per processor/department/month rollup.
- `history.py`: Per-batch processing log + saved registers for re-download.
- `admin.py`: Processor onboarding + lifecycle management (no code).
- `consolidated_excel.py`: One-row-per-PDF registers; preserves template styling
  via header-name matching; per-type workbooks (ZIP for multi-type batches).
- `document_state.py`: `DocumentState` (per-document state incl. auto-fix notes,
  audit, usage) and `DocumentManager` (collection + batch downloads).
- `preview.py`: PDF/image preview rendering.
- `ui.py`: India Glycols branding + premium design system (~70% SAP Fiori,
  ~30% Apple HIG). No business logic.
- `config.py`: App config + shared singletons (`gemini_key_manager`,
  `ai_gateway`). Secrets from env only.
- `ai_gateway.py` / `api_key_manager.py` / `gemini_errors.py`: AI Gateway
  (key + model failover), key discovery/rotation, error classification.
- `gemini.py`: Gemini client boundary; accepts raw bytes or preprocessed image
  parts; captures token usage; delegates execution to the gateway.

### Plugin framework
- `processors/base.py`: `BaseProcessor` interface (spec, build_client,
  schema_path, validate, auto_fix, build_excel_bytes, build_row).
- `processors/spec.py`: `ProcessorSpec` (+ `ExportSpec`, `FieldSpec`, …),
  `from_manifest`, dotted-path + export-value helpers.
- `processors/folder_processor.py`: `FolderProcessor` — manifest-driven plugin.
- `processors/discovery.py`: Filesystem discovery of all manifests.
- `processors/bootstrap.py`: `bootstrap_processors()` / `refresh_processors()`.
- `processors/registry.py`: Registry + department/status lookups.
- `processors/generic_validator.py`: Spec-driven validate + deterministic auto-fix.
- `processors/generic_exporter.py`: Spec-driven per-document workbook.

### Per-processor folder (`processors/<key>/`)
- `manifest.json`: Single source of metadata (versioned).
- `schema/schema.json`: Explicit, hand-authored output schema.
- `prompts/v1/{system,extraction}_prompt.txt`: Versioned prompts.
- `validator.py` (optional): `validate(data)` and/or `auto_fix(data)`.
- `exporter.py` (optional): `build_excel_bytes(data)`.
- `templates/`, `samples/{raw,expected_json,expected_excel}/`, `README.md`.

### Shared utilities
- `utils/confidence.py`: Hybrid confidence engine + bands + `overall_confidence`.
- `utils/validators.py`: Shared `normalize_to_schema` (document-agnostic).
- `utils/json_handler.py`, `utils/file_handler.py`, `utils/helpers.py`.

### Data
- `departments.py`: Static 11-department catalog (processes grouped from manifests).
- `outputs/`: Generated artifacts, cache, usage, history (git-ignored).
- `assets/`: Branding (drop `logo.*`).

## Coding Principles & Non-Negotiable Rules

- Clean architecture, modular, single responsibility; UI separate from logic.
- Gemini ONLY extracts business information (and reports confidence). ALL AI
  requests go through the `ai_gateway` single entry point.
- Models are configurable (`GEMINI_MODEL_1..N`), never hardcoded in extraction.
- Python performs preprocessing, auto-fix, validation, and Excel generation.
- Excel is ALWAYS generated from standardized JSON, never directly from Gemini.
- The JSON schema is the single source of truth; schemas are explicit/hand-authored.
- Each processor owns its prompts, schema, validation, and export mapping.
- Processors share only the `BaseProcessor` interface — never each other's logic.
- API key values are never logged, displayed, saved, or placed in exceptions.

## Setup & Run

```bash
pip install -r requirements.txt
# .env with one or more keys and (optionally) a model priority list:
#   GEMINI_API_KEY_1=...   (add _2 ... _N for failover)
#   GEMINI_MODEL_1=gemini-2.5-flash   (add _2 ... _N, tried in order)
# Optional cost rates: GEMINI_INPUT_COST_PER_1K_INR, GEMINI_OUTPUT_COST_PER_1K_INR
# APP_ENV=production hides Developer Mode by default.
streamlit run app.py
```
