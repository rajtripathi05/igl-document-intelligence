# India Glycols — Enterprise Document Intelligence Platform

## Project Goal

An AI-powered Intelligent Document Processing (IDP) platform that converts
business documents from any vendor or format into standardized, ERP-ready
structured JSON and Excel.

Built for **India Glycols Limited** to serve multiple departments. The platform
is a plugin system: each document type is an independent, self-contained
processor that plugs into a shared engine. It is designed to scale to hundreds
of document processors without architectural changes.

Long-term goal: SAP integration.

## Current Status — Version 1.2

Live, working processors:

- **Procurement → Purchase Order**
- **Export → Shipping Bill**

Platform capabilities (work automatically for every processor):

1. Department selection
2. Multi-document upload (PDF / image)
3. **Automatic document classification** — AI detects the document type and
   routes to the correct processor (no manual document-type selection)
4. AI extraction via Google Gemini using per-processor prompts + schema
5. **Field-level confidence scores** (hybrid: AI-reported + heuristic fallback)
6. **Color-coded confidence** (green 95–100, yellow 70–94, red 0–69)
7. **Editable extraction** — every field and line item is editable; edits update
   the standardized JSON live
8. **Re-export** — regenerate JSON / Excel from edited data without calling AI again
9. **Document preview** — PDF/image preview with page thumbnails; toggle between
   Original Document and Extracted Data
10. **Multiple-document handling** — each document keeps its own file, processor,
    confidence, validation, JSON, and Excel; per-document and batch downloads
    (Download All JSON / All Excel / ZIP)
11. **OCR understanding** — handwriting, mobile photos, low-quality scans, rotated
    pages, stamps, and business abbreviations (Qty→Quantity, etc.)

## Technology

- Python 3.11+
- Streamlit
- Google Gemini API (`google-genai` SDK)
- OpenPyXL (Excel generation)
- Pandas (editable line-item tables)
- PyMuPDF (PDF preview + quick text for classification)
- python-dotenv

## Architecture

```text
Select Department
    |
    v
Upload Document(s)
    |
    v
Document Classifier  ──>  detects document type from processor metadata
    |
    v
Processor Registry   ──>  routes to the matching processor (or "Unsupported")
    |
    v
AI Gateway           ──>  single AI entry point; key + model failover
    |
    v
Gemini Extraction    ──>  business data + per-field confidence (AI)
    |
    v
Normalize to Schema  ──>  schema is the single source of truth
    |
    v
Generic Engine       ──>  confidence display, editing, preview, validation
    |
    v
Re-export            ──>  JSON + Excel (edited data, no AI re-call)
    |
    v
SAP Integration (Future)
```

### Plugin model

A processor is **declarative**. It exposes a `ProcessorSpec` (fields, sections,
line-item columns, classification keywords, AI description) plus a Gemini client,
schema path, validation function, and Excel generator. It does **not** render its
own UI — the generic engine renders every feature uniformly.

Adding a new document type requires only:

1. Add prompts under `prompts/`.
2. Add a JSON schema under `schemas/`.
3. Add a validation module under `utils/` (its own rules).
4. Add an Excel generator (its own module).
5. Add a processor under `processors/` implementing `BaseProcessor` with a `ProcessorSpec`.
6. Register it in `processors/bootstrap.py` (one line).

No existing processor, prompt, schema, or the engine is modified. The new
processor automatically inherits classification, confidence, editing, preview,
re-export, validation, multi-upload, and downloads.

## Folder & Module Responsibilities

### Application shell / engine
- `app.py`: Orchestration shell — department nav, multi-upload, premium
  drag-and-drop upload, animated processing queue, per-document tabs, batch
  downloads. No document-specific logic.
- `engine.py`: Generic engine. Renders confidence-scored editable fields, line
  items, preview/data toggle, validation, and per-document export for any
  processor — driven by its `ProcessorSpec`.
- `processing.py`: Per-document orchestration (classify → extract → confidence →
  normalize → validate). The only place Gemini is called.
- `classifier.py`: Automatic document classifier (AI primary, keyword fallback),
  driven entirely by processor metadata.
- `document_state.py`: `DocumentState` (per-document state) and `DocumentManager`
  (collection + batch JSON/Excel/ZIP downloads).
- `preview.py`: PDF/image preview rendering (PyMuPDF thumbnails + full pages).
- `ui.py`: India Glycols branding and the premium enterprise design system
  (~70% SAP Fiori, ~30% Apple HIG) — global theme/CSS, header, sidebar brand
  lockup, breadcrumbs, section headings, confidence chips/meters, the AI Gateway
  dashboard card, processing-queue/document-status helpers, and subtle
  animations. The navigation is the Department selector; the sidebar shows no
  decorative (non-routing) nav items.
- `config.py`: Environment + path configuration and the shared singletons
  (`gemini_key_manager`, `ai_gateway`). Secrets read from env only.
- `ai_gateway.py`: **Enterprise AI Gateway** — the single entry point for every
  AI request. Fails over across both API keys and Gemini models before reporting
  failure (immediate key/model rotation; exponential backoff only between full
  retry cycles, max 3). Discovers the configurable model priority list
  (`GEMINI_MODEL_1..N`). Exposes a non-sensitive status snapshot for the dev UI.
- `api_key_manager.py`: Discovers/rotates/tracks API keys. No module reads key
  env vars directly. Keys are referenced only by number, never by value.
- `gemini_errors.py`: Retryable-vs-fatal error classification used by the gateway.
- `gemini.py`: Google Gemini client boundary. Document-agnostic extraction
  (`extract`, `extract_with_confidence`). Builds the instruction and delegates
  execution to the gateway — it never selects a key or model itself. OCR/
  confidence guidance is appended at call time so prompt files are never modified.

### Per-document-type boundaries
- `excel.py`: Purchase Order Excel generator.
- `excel_shipping_bill.py`: Shipping Bill Excel generator.

### Plugin framework
- `processors/base.py`: `BaseProcessor` interface (the only shared contract).
- `processors/spec.py`: `ProcessorSpec`, `FieldSpec`, `SectionSpec`,
  `LineItemColumn`, and dotted-path helpers.
- `processors/registry.py`: Processor registry + department/use-case lookups.
- `processors/bootstrap.py`: Single place all processors are registered.
- `processors/purchase_order.py`: Purchase Order processor (declarative).
- `processors/shipping_bill.py`: Shipping Bill processor (declarative).

### Shared utilities
- `utils/confidence.py`: Hybrid confidence engine (AI map + heuristics).
- `utils/validators.py`: Purchase Order validation + schema normalization.
- `utils/shipping_bill_validators.py`: Shipping Bill validation engine.
- `utils/json_handler.py`: JSON parse/load/serialize/save.
- `utils/file_handler.py`: MIME detection, slugs, output paths.
- `utils/helpers.py`: Logging config, file reads, formatting.

### Data & assets
- `departments.py`: Department / use-case registry.
- `prompts/`: Per-processor AI prompts (read from files, never hardcoded).
- `schemas/`: Per-processor JSON schemas (single source of truth).
- `samples/`: Test documents used during development.
- `templates/`: SAP Excel templates / mapping templates (future).
- `assets/`: Static assets. Drop `logo.png` here to brand the header.
- `outputs/`: Generated JSON/Excel (git-ignored; not committed).

## Coding Principles

- Clean architecture, modular design, single responsibility
- Separate UI from business logic; separate Gemini, validation, and Excel
- Never hardcode prompts or API keys
- Read prompts from `prompts/`, schema from `schemas/`, API key from `.env`
- Type hints, docstrings, error handling, logging
- Readability over cleverness; extensible design

## Non-Negotiable Rules

- Gemini ONLY extracts business information (and reports confidence).
- ALL AI requests go through the `ai_gateway` single entry point. No processor,
  the classifier, or any future module talks to Gemini (`genai`) directly except
  inside the gateway-supplied `call(api_key, model)` closure.
- Models are configurable (`GEMINI_MODEL_1..N`) and never hardcoded in the
  extraction engine — only the gateway/config know default models.
- Python performs validation, transformation, and Excel generation.
- Excel is ALWAYS generated from standardized JSON, never directly from Gemini.
- The JSON schema is the single source of truth.
- Each document type owns its own prompts, schema, validation, and Excel.
- Processors share only the `BaseProcessor` interface — never each other's logic.
- Do not modify a schema without maintaining backward compatibility.

## Setup & Run

```bash
pip install -r requirements.txt
# Create .env with one or more keys and (optionally) a model priority list:
#   GEMINI_API_KEY_1=your_key       (add GEMINI_API_KEY_2 ... _N for failover)
#   GEMINI_MODEL_1=gemini-2.5-flash (add GEMINI_MODEL_2 ... _N, tried in order)
#   GEMINI_MODEL_2=gemini-2.5-flash-lite
#   ...                             (numbering is open-ended; e.g. up to _10)
# The AI Gateway fails over across all keys and models automatically.
streamlit run app.py
```

## Future Roadmap

- More Export document types (Commercial Invoice, Packing List, Bill of Lading,
  Certificate of Origin, Export Invoice, Export Declaration, Customs Documents)
- More departments (Sales, Finance/Accounts, HR, Operations, Mechanical, Chemical)
- SAP Excel templates and SAP mapping per processor
- SAP integration
