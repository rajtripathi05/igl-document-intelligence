# po-processor

Enterprise AI Document Processing Platform for converting business documents
into ERP-ready structured data.

Version 1 supports only Purchase Orders.

## Project Overview

`po-processor` is the foundation for an SAP Document Intelligence Platform. The
application will process Purchase Order PDFs and images, extract business data
with Google Gemini, validate the result against a standard schema, and generate
ERP-ready JSON and Excel outputs.

This repository currently contains a production-ready project structure,
configuration, documentation, and placeholder modules only. Application logic,
API calls, UI workflows, validation, and Excel generation are intentionally not
implemented yet.

## Objectives

- Create a clean and scalable architecture for enterprise document processing.
- Keep UI, AI integration, validation, and Excel generation separated.
- Use the Purchase Order JSON schema as the single source of truth.
- Prepare the codebase for future SAP integration.
- Support additional document types in later versions.

## Folder Structure

```text
po-processor/
|-- app.py
|-- gemini.py
|-- excel.py
|-- config.py
|-- requirements.txt
|-- README.md
|-- CLAUDE.md
|-- .gitignore
|-- .env.example
|-- prompts/
|   |-- system_prompt.txt
|   `-- extraction_prompt.txt
|-- schemas/
|   `-- purchase_order_schema.json
|-- templates/
|   `-- README.md
|-- samples/
|   `-- README.md
|-- outputs/
|   `-- README.md
|-- utils/
|   |-- file_handler.py
|   |-- json_handler.py
|   |-- validators.py
|   `-- helpers.py
`-- assets/
    `-- README.md
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Running the Project

```bash
streamlit run app.py
```

The Streamlit application is currently a skeleton. User-facing functionality
will be added in a later implementation phase.

## Environment Variables

Create a `.env` file with one or more API keys and (optionally) a model
priority list. The Enterprise AI Gateway automatically fails over across every
key and model before reporting a failure.

```text
# One key is enough; add more for automatic failover.
GEMINI_API_KEY_1=YOUR_FIRST_KEY
GEMINI_API_KEY_2=YOUR_SECOND_KEY
# ... up to GEMINI_API_KEY_N

# Optional model priority order (tried top to bottom).
GEMINI_MODEL_1=gemini-2.5-flash
GEMINI_MODEL_2=gemini-2.5-flash-lite
GEMINI_MODEL_3=gemini-2.5-flash-preview
```

A single bare `GEMINI_API_KEY` / `GEMINI_MODEL` is still supported for backward
compatibility. API keys must be stored in `.env` and never hardcoded; they are
referenced only by number in logs and the UI, never by value.

## Current Features

- Production-ready folder structure.
- Placeholder Streamlit application entry point.
- Placeholder Gemini client module.
- Placeholder Excel generator module.
- Environment variable loading with `python-dotenv`.
- Empty prompt files ready for future prompt engineering.
- Placeholder Purchase Order schema file.
- Documentation for future development.

## Future Roadmap

- Version 1: Purchase Order processing.
- Version 2: Validation engine.
- Version 3: Excel templates.
- Version 4: Multiple document types.
- Version 5: Department and document classification.
- Version 6: SAP integration.
