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

## Current Status — Version 2.3

V2.3 (Enterprise AI Gateway & UX upgrade) adds, on top of everything below:
a **provider-agnostic AI Gateway** (OpenRouter default; Gemini retained;
Claude/OpenAI/DeepSeek/etc. are drop-in `providers/` classes) selected purely
from `.env` (`AI_PROVIDER`/`AI_API_KEY`/`DEFAULT_MODEL`/`RETRY_MODEL`); a single
controlled **stronger-model retry** (reuses OCR/preprocess, replaces data only on
success, one retry per document); a **cost predictor** (₹ before processing) plus
per-model / retry / today cost analytics; **duplicate detection** (content
fingerprint with Continue Anyway / Cancel); **SAP-readiness** scoring per document;
and a **split Acrobat-style review** (PDF viewer with hybrid text-anchor + AI
bounding-box field highlighting, click-to-scroll, confidence heatmap). The
workflow is unchanged: Department → Business Process → Upload → Process → Review →
Download.

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
13. **Provider-agnostic AI Gateway** — one entry point for all AI. `AI_PROVIDER`
    selects the backend (OpenRouter / Gemini / future Claude, OpenAI, DeepSeek…);
    `DEFAULT_MODEL` serves normal processing and `RETRY_MODEL` serves the single
    stronger-model retry. Transient errors (429/5xx/timeouts) are retried with
    exponential backoff; fatal errors surface immediately. Processors never know
    the provider or model — they only call `extract()` / retry. Keys are never
    logged, displayed, saved, or placed in exceptions.
14. **Single controlled retry** — one "Retry with stronger model" per document in
    review; reuses OCR/preprocessing, runs `RETRY_MODEL`, replaces the extraction
    only on success (never overwrites good data), then disables further retries.
15. **Cost predictor** — estimated tokens + ₹ shown before processing; cost
    dashboard splits by model (DEFAULT vs RETRY), tracks retry usage, today's
    spend, and per-document averages (cost / tokens / time).
16. **Duplicate detection** — a content fingerprint warns "Already Processed"
    (date / processor / department) with Continue Anyway or Cancel before running.
17. **SAP readiness** — each document is scored (Ready ≥95 / Needs Review 75–94 /
    Not Ready <75) from processor-declared SAP-critical fields, with reasons.
18. **Split Acrobat-style review** — original PDF on the left with confidence-
    coloured overlay boxes (hybrid: PyMuPDF text-anchor + on-demand AI bounding
    boxes) and click-to-scroll; editable business fields on the right sharing the
    same confidence heatmap palette.

## Technology

- Python 3.11+, Streamlit
- Provider-agnostic AI Gateway: OpenRouter (OpenAI-compatible REST via `httpx`,
  default) and Google Gemini (`google-genai` SDK); new providers are drop-in
  `providers/` classes
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
- `config.py`: App config + shared singleton `ai_gateway`; builds the active
  provider via `providers.build_provider()`. Secrets from env only.
- `ai_gateway.py`: Provider + DEFAULT/RETRY model orchestrator (transient-error
  backoff, live stage/queue status). `gemini_errors.py`: error classification
  (transient vs. fatal), reused by providers.
- `providers/`: provider-agnostic backends — `base.py` (`Provider` contract,
  `ProviderResponse`, `AIError`/`TransientAIError`/`FatalAIError`),
  `openrouter.py` (OpenAI-compatible REST via httpx, default), `gemini.py`
  (google-genai, single key), `factory.py` (`AI_PROVIDER` → provider),
  `_images.py` (PDF→image for OpenAI-style providers).
- `gemini.py`: Per-processor extraction client boundary; builds the instruction
  and delegates to the gateway (provider-neutral); captures token usage; carries
  a `use_retry_model` flag.
- `sap.py`: SAP-readiness assessment (spec-driven critical fields, score/reasons).
- `duplicates.py`: content-fingerprint index for duplicate detection.
- `field_locator.py`: hybrid field location (PyMuPDF text-anchor + AI bbox).
- `pdf_viewer.py`: Acrobat-style review viewer (HTML overlay boxes + scroll).

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
- The AI provider ONLY extracts business information (and reports confidence).
  ALL AI requests go through the `ai_gateway` single entry point, and no
  processor knows which provider or model is used.
- Provider and models are configurable via `.env` (`AI_PROVIDER`, `AI_API_KEY`,
  `DEFAULT_MODEL`, `RETRY_MODEL`), never hardcoded in extraction.
- Python performs preprocessing, auto-fix, validation, and Excel generation.
- Excel is ALWAYS generated from standardized JSON, never directly from Gemini.
- The JSON schema is the single source of truth; schemas are explicit/hand-authored.
- Each processor owns its prompts, schema, validation, and export mapping.
- Processors share only the `BaseProcessor` interface — never each other's logic.
- API key values are never logged, displayed, saved, or placed in exceptions.

## Setup & Run

```bash
pip install -r requirements.txt
# .env — provider-agnostic AI configuration (V2.3). Switch provider or models by
# editing ONLY this file; no source changes.
#   AI_PROVIDER=openrouter        # or: gemini  (future: claude, openai, deepseek…)
#   AI_API_KEY=...                # a single key for the selected provider
#   DEFAULT_MODEL=google/gemini-flash-latest   # normal processing
#   RETRY_MODEL=google/gemini-pro-latest       # the one-click "stronger" retry
# Optional cost rates: AI_INPUT_COST_PER_1K_INR, AI_OUTPUT_COST_PER_1K_INR
#   (GEMINI_*_COST_PER_1K_INR still honoured as a fallback).
# Legacy GEMINI_API_KEY_* are used only when AI_PROVIDER=gemini and AI_API_KEY
# is empty (the built-in Gemini provider picks the first one — handy for testing
# before an OpenRouter key is provisioned).
# APP_ENV=production hides Developer Mode by default.
streamlit run app.py
```
