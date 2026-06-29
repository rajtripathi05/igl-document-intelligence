<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=220&color=0:0EA5E9,35:7C3AED,70:E11D48,100:F97316&text=IGL%20Document%20Intelligence&fontColor=FFFFFF&fontSize=42&fontAlignY=38&desc=AI%20Document%20Processing%20%7C%20Review%20%7C%20Validate%20%7C%20Export&descSize=16&descAlignY=58" alt="IGL Document Intelligence banner" />
</p>

<div align="center">
  <img src="assets/logo.jpg" alt="IGL Logo" width="115" />

  <br />
  <br />

  <a href="#mission-control">
    <img src="https://img.shields.io/badge/Mission-Control-0EA5E9?style=for-the-badge" alt="Mission Control" />
  </a>
  <a href="#launch-sequence">
    <img src="https://img.shields.io/badge/Launch-Sequence-7C3AED?style=for-the-badge" alt="Launch Sequence" />
  </a>
  <a href="#processor-grid">
    <img src="https://img.shields.io/badge/Processor-Grid-E11D48?style=for-the-badge" alt="Processor Grid" />
  </a>
  <a href="#security-vault">
    <img src="https://img.shields.io/badge/Security-Vault-F97316?style=for-the-badge" alt="Security Vault" />
  </a>

  <br />
  <br />

  <img src="https://readme-typing-svg.demolab.com?font=Inter&weight=700&size=24&pause=900&color=22C55E&center=true&vCenter=true&width=900&lines=Upload+business+documents.;Classify+with+Gemini.;Extract+structured+ERP-ready+data.;Review+confidence+and+validation.;Export+JSON%2C+Excel%2C+and+ZIP." alt="Typing animation" />

  <br />
  <br />

  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Streamlit-Production%20UI-FF4B4B?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/Google-Gemini-4285F4?style=flat-square&logo=google&logoColor=white" alt="Google Gemini" />
  <img src="https://img.shields.io/badge/Exports-JSON%20%2B%20Excel%20%2B%20ZIP-16A34A?style=flat-square" alt="Exports" />
  <img src="https://img.shields.io/badge/Gateway-Key%20Rotation%20%2B%20Failover-F97316?style=flat-square" alt="Gateway Failover" />
  <img src="https://img.shields.io/badge/Review-Editable%20Confidence%20UI-E11D48?style=flat-square" alt="Review UI" />
</div>

---

<a id="mission-control"></a>

## Mission Control

<table>
  <tr>
    <td width="25%" align="center">
      <img src="https://img.shields.io/badge/01-Upload-0EA5E9?style=for-the-badge" alt="Upload" />
      <br />
      PDFs, scanned documents, and image files
    </td>
    <td width="25%" align="center">
      <img src="https://img.shields.io/badge/02-Classify-7C3AED?style=for-the-badge" alt="Classify" />
      <br />
      Gemini-powered document routing with keyword fallback
    </td>
    <td width="25%" align="center">
      <img src="https://img.shields.io/badge/03-Review-E11D48?style=for-the-badge" alt="Review" />
      <br />
      Confidence scores, validation, preview, and editable fields
    </td>
    <td width="25%" align="center">
      <img src="https://img.shields.io/badge/04-Export-22C55E?style=for-the-badge" alt="Export" />
      <br />
      JSON, Excel, and batch ZIP packages
    </td>
  </tr>
</table>

`po-processor` is a Streamlit-based AI document intelligence platform built for
business teams that need clean, reviewable, ERP-ready data from unstructured
documents.

**Version 2.0** is a manifest-driven, auto-discovering plugin platform. It runs
in **Manual** mode (Department → Business Process — the accurate default) or
**Auto Detect** mode (the AI picks the process). Live processors today are
**Store → IGP**, **Marketing → Sales Order**, and **Export → Shipping Bill**;
every other process across 11 departments is registered as *coming soon*.
Adding a processor is just adding a folder with a `manifest.json` (or using the
built-in Admin panel) — no code changes and no hardcoded routing.

---

## Signal Panel

<table>
  <tr>
    <td align="center"><b>Document Intake</b></td>
    <td align="center"><b>AI Reliability</b></td>
    <td align="center"><b>Human Review</b></td>
    <td align="center"><b>Structured Output</b></td>
  </tr>
  <tr>
    <td align="center">
      <img src="https://img.shields.io/badge/PDF-Ready-B91C1C?style=for-the-badge" alt="PDF" />
      <br />
      <img src="https://img.shields.io/badge/Images-Ready-0F766E?style=for-the-badge" alt="Images" />
    </td>
    <td align="center">
      <img src="https://img.shields.io/badge/Keys-Rotated-F97316?style=for-the-badge" alt="Keys Rotated" />
      <br />
      <img src="https://img.shields.io/badge/Models-Failover-7C3AED?style=for-the-badge" alt="Models Failover" />
    </td>
    <td align="center">
      <img src="https://img.shields.io/badge/Fields-Editable-E11D48?style=for-the-badge" alt="Editable Fields" />
      <br />
      <img src="https://img.shields.io/badge/Confidence-Visible-22C55E?style=for-the-badge" alt="Confidence" />
    </td>
    <td align="center">
      <img src="https://img.shields.io/badge/JSON-Schema--Ready-2563EB?style=for-the-badge" alt="JSON" />
      <br />
      <img src="https://img.shields.io/badge/Excel-Generated-16A34A?style=for-the-badge" alt="Excel" />
    </td>
  </tr>
</table>

---

## Supported Documents

<table>
  <tr>
    <th>Zone</th>
    <th>Document</th>
    <th>Processor</th>
    <th>Review UI</th>
    <th>Exports</th>
  </tr>
  <tr>
    <td><b>Store</b></td>
    <td>IGP (Inward Gate Pass)</td>
    <td><img src="https://img.shields.io/badge/Production-22C55E?style=flat-square" alt="Production" /></td>
    <td>Fields, line items, confidence, validation, preview</td>
    <td>Excel Register, per-doc XLSX</td>
  </tr>
  <tr>
    <td><b>Marketing</b></td>
    <td>Sales Order</td>
    <td><img src="https://img.shields.io/badge/Production-22C55E?style=flat-square" alt="Production" /></td>
    <td>Fields, line items, confidence, validation, preview</td>
    <td>Excel Register, per-doc XLSX</td>
  </tr>
  <tr>
    <td><b>Export</b></td>
    <td>Shipping Bill</td>
    <td><img src="https://img.shields.io/badge/Production-22C55E?style=flat-square" alt="Production" /></td>
    <td>Fields, line items, confidence, validation, preview</td>
    <td>Excel Register, per-doc XLSX</td>
  </tr>
  <tr>
    <td colspan="5" align="center"><i>Store · Marketing · Finance · Export · Supply Chain · HR · Operations · Mechanical · Chemical · Production · Management — remaining processes register as <b>Coming Soon</b></i></td>
  </tr>
</table>

---

## System Flow

```mermaid
flowchart LR
    A[Upload Documents] --> B{Department Context}
    B --> C[Processor Candidates]
    C --> D[Gemini Classifier]
    D -->|Success| E[Matched Processor]
    D -->|Fallback| F[Keyword Classifier]
    F --> E
    E --> G[Gemini Extraction]
    G --> H[Schema Normalization]
    H --> I[Confidence Scoring]
    I --> J[Validation Engine]
    J --> K[Editable Review Workspace]
    K --> L[JSON Export]
    K --> M[Excel Export]
    K --> N[Batch ZIP Export]

    style A fill:#0EA5E9,color:#fff,stroke:#0369A1
    style D fill:#7C3AED,color:#fff,stroke:#5B21B6
    style G fill:#E11D48,color:#fff,stroke:#9F1239
    style K fill:#F97316,color:#fff,stroke:#C2410C
    style L fill:#22C55E,color:#fff,stroke:#15803D
    style M fill:#22C55E,color:#fff,stroke:#15803D
    style N fill:#22C55E,color:#fff,stroke:#15803D
```

---

## Feature Reactor

| Module | What It Delivers | Status |
| --- | --- | --- |
| Manual + Auto Detect modes | Department → Business Process, or AI-chosen process | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| Manifest auto-discovery | Processors loaded from `processors/<key>/manifest.json` | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| OCR preprocessing | Auto-orient, deskew, denoise, contrast (scanned PDFs/images) | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| Extraction engine | Multi-page, handwriting-aware, schema-shaped JSON | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| Auto-Fix | Deterministic repairs with per-fix confidence before validation | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| Confidence layer | Overall + field-level confidence bands (95 / 75 thresholds) | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| Inline editor + audit | Edit fields/line items; AI→user edits recorded | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| Excel registers | One workbook per type, one row per PDF, template styling preserved | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| Extraction cache | Repeat uploads skip Gemini (hash + processor + prompt version) | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| Dashboards | History (re-download), Cost (₹), Processor Health | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| Admin panel | Onboard processors by upload; draft → testing → production | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |
| AI Gateway | Multi-key + multi-model rotation, fallback, graceful failover | ![Ready](https://img.shields.io/badge/Ready-22C55E?style=flat-square) |

---

## Tech Wall

<p align="center">
  <img src="https://skillicons.dev/icons?i=python" alt="Python" />
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/Google%20GenAI-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google GenAI" />
  <img src="https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="pandas" />
  <img src="https://img.shields.io/badge/openpyxl-217346?style=for-the-badge" alt="openpyxl" />
  <img src="https://img.shields.io/badge/PyMuPDF-0F766E?style=for-the-badge" alt="PyMuPDF" />
  <img src="https://img.shields.io/badge/Pillow-9F1239?style=for-the-badge" alt="Pillow" />
  <img src="https://img.shields.io/badge/python--dotenv-111827?style=for-the-badge" alt="python-dotenv" />
</p>

---

<a id="launch-sequence"></a>

## Launch Sequence

<table>
  <tr>
    <td width="50%">

### Clone

```bash
git clone <your-repository-url>
cd po-processor
```

### Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

  </td>
  <td width="50%">

### Configure

```env
GEMINI_API_KEY_1=your_first_gemini_api_key
GEMINI_API_KEY_2=your_second_gemini_api_key
GEMINI_MODEL_1=gemini-2.5-flash
GEMINI_MODEL_2=gemini-2.5-flash-lite
APP_ENV=production
```

### Run

```bash
streamlit run app.py
```

  </td>
  </tr>
</table>

Open the local Streamlit URL:

```text
http://localhost:8501
```

For macOS/Linux activation, use:

```bash
source .venv/bin/activate
```

---

## Operator Workflow

```mermaid
sequenceDiagram
    participant User
    participant Streamlit
    participant Classifier
    participant Gateway
    participant Gemini
    participant Processor
    participant Exporter

    User->>Streamlit: Upload PDF/image documents
    Streamlit->>Classifier: Send candidates by department
    Classifier->>Gateway: Request AI classification
    Gateway->>Gemini: Try model/key combinations
    Gemini-->>Gateway: Classification JSON
    Gateway-->>Classifier: Safe result
    Classifier-->>Streamlit: Matched processor
    Streamlit->>Processor: Extract and normalize
    Processor->>Gateway: Gemini extraction request
    Gateway->>Gemini: Failover-protected call
    Gemini-->>Processor: Structured response
    Processor-->>Streamlit: Data, confidence, validation
    User->>Streamlit: Review and edit
    Streamlit->>Exporter: Generate JSON / Excel / ZIP
```

---

<a id="processor-grid"></a>

## Processor Grid

Every document type plugs into the same engine by declaring a `ProcessorSpec`.

<table>
  <tr>
    <th>Processor Asset</th>
    <th>Purpose</th>
  </tr>
  <tr>
    <td><code>ProcessorSpec</code></td>
    <td>Declares fields, sections, line items, labels, and classification metadata.</td>
  </tr>
  <tr>
    <td>Prompt files</td>
    <td>Control Gemini system behavior and extraction instructions.</td>
  </tr>
  <tr>
    <td>JSON schema</td>
    <td>Defines normalized output shape.</td>
  </tr>
  <tr>
    <td>Validator</td>
    <td>Reports document-specific business issues.</td>
  </tr>
  <tr>
    <td>Excel generator</td>
    <td>Builds ERP-friendly workbook exports.</td>
  </tr>
</table>

```mermaid
mindmap
  root((Processor))
    Metadata
      Document type
      Department
      Keywords
    Extraction
      System prompt
      Extraction prompt
      Gemini client
    Schema
      JSON normalization
      Required sections
      Line items
    Review
      Field specs
      Confidence display
      Editable tables
    Output
      JSON
      Excel
      ZIP
```

---

## Project Map

```text
po-processor/
|-- app.py                         # Shell: modes, nav, registers, dashboards
|-- ai_gateway.py                  # Gemini key/model failover gateway
|-- api_key_manager.py             # API key discovery and rotation
|-- classifier.py                  # AI + keyword document classifier (Auto Detect)
|-- config.py                      # App settings + shared singletons
|-- preprocess.py                  # OCR preprocess (orient/deskew/denoise/contrast)
|-- cache.py                       # Extraction cache (skip Gemini on repeats)
|-- cost.py                        # Token capture + INR cost rollups
|-- history.py                     # Per-batch processing log + register re-download
|-- admin.py                       # Processor onboarding + lifecycle (no code)
|-- consolidated_excel.py          # One-row-per-PDF registers (template styling)
|-- document_state.py              # Document state, audit, batch exports
|-- engine.py                      # Generic review/edit/export workspace
|-- gemini.py                      # Gemini client (parts + usage capture)
|-- processing.py                  # preprocess->classify/assign->extract->auto-fix
|-- preview.py                     # PDF/image preview rendering
|-- ui.py                          # Theme and Streamlit UI helpers
|-- departments.py                 # 11-department catalog
|-- processors/
|   |-- base.py                    # Processor interface
|   |-- spec.py                    # ProcessorSpec + from_manifest + export specs
|   |-- folder_processor.py        # Manifest-driven plugin
|   |-- discovery.py               # Filesystem discovery of manifests
|   |-- bootstrap.py               # Discovery entry point / refresh
|   |-- registry.py                # Registry + department/status lookups
|   |-- generic_validator.py       # Spec-driven validate + auto-fix
|   |-- generic_exporter.py        # Spec-driven per-doc workbook
|   |-- igp/                       # Store -> IGP (production)
|   |-- purchase_order/            # Marketing -> Sales Order (production)
|   |-- shipping_bill/             # Export -> Shipping Bill (production)
|   `-- <key>/                     # manifest.json, schema/, prompts/v1/,
|                                  #   validator.py?, exporter.py?, templates/, samples/
|-- utils/                         # normalize_to_schema, confidence, JSON, files
|-- assets/                        # Branding assets
|-- outputs/                       # Generated artifacts, cache, usage, history (git-ignored)
|-- requirements.txt
`-- README.md
```

---

<a id="security-vault"></a>

## Security Vault

<table>
  <tr>
    <td align="center">
      <img src="https://img.shields.io/badge/Secrets-.env%20Only-111827?style=for-the-badge" alt="Secrets" />
    </td>
    <td>API keys are loaded from environment variables only.</td>
  </tr>
  <tr>
    <td align="center">
      <img src="https://img.shields.io/badge/Logs-No%20Key%20Values-B91C1C?style=for-the-badge" alt="Logs" />
    </td>
    <td>Key values are never logged, displayed, saved, or placed in exceptions.</td>
  </tr>
  <tr>
    <td align="center">
      <img src="https://img.shields.io/badge/Gateway-Key%20Numbers-F97316?style=for-the-badge" alt="Gateway" />
    </td>
    <td>Operational status references keys only by number, such as Key #1.</td>
  </tr>
  <tr>
    <td align="center">
      <img src="https://img.shields.io/badge/GitHub-Keep%20Clean-22C55E?style=for-the-badge" alt="GitHub" />
    </td>
    <td>Keep `.env`, generated exports, debug logs, and sensitive documents out of Git.</td>
  </tr>
</table>

---

## Roadmap Console

```mermaid
timeline
    title IGL Document Intelligence Roadmap
    Current
      : Manifest-driven auto-discovery + Admin onboarding
      : IGP, Sales Order, Shipping Bill processors
      : Manual + Auto Detect modes
      : OCR preprocess, auto-fix, per-type Excel registers
      : History, Cost, Health dashboards
    Next
      : Promote coming-soon processors to production
      : ERP-specific Excel mappings + regression fixtures
      : Background batch processing worker
    Later
      : SAP integration hooks
      : Deployment packaging
```

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&height=90&color=0:22C55E,50:0EA5E9,100:7C3AED&text=Fast%20Review%20%7C%20Clean%20Exports%20%7C%20ERP%20Ready&fontColor=FFFFFF&fontSize=24" alt="Footer banner" />
</p>

<div align="center">
  <img src="https://img.shields.io/badge/Status-Active%20Development-22C55E?style=for-the-badge" alt="Active Development" />
  <img src="https://img.shields.io/badge/License-Add%20Before%20Publishing-F59E0B?style=for-the-badge" alt="License" />
  <img src="https://img.shields.io/badge/Made%20For-IGL%20Document%20Ops-0EA5E9?style=for-the-badge" alt="Made for IGL" />
</div>
