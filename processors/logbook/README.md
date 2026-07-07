# Log Book processor (Plant Operations)

Converts **mostly-handwritten plant Log Book / Batch Card page photos** into one
combined, Book11-style Excel register — **one row per batch**. Built for the
R-850 Stirred Reactor Log Book and the General Batch Card for
Blending/Formulated/Reaction, and designed to tolerate ~1000 different products.

## How it works (`engine: "logbook"`)

1. **Per-page AI read.** Each uploaded image is sent to the shared AI gateway
   individually (schema in `schema/schema.json`, prompts in `prompts/v1/`), and
   classified as a printed **grid/main** page or a lined **remarks** page
   (`page_type`). Results are cached by image content, so re-runs are instant.
2. **Batch assembly.** Each main page becomes a batch. Each remarks page is
   paired to its main page using content **join-keys** — batch no, date,
   unloading/filling start & finish times, total filled kg — with a weak
   upload-order tiebreak. This works even when hundreds of images arrive flat and
   out of order (validated: 6 shuffled ECARE 243 photos → 3 correct batches).
3. **Register.** One row per batch, written in the uploaded Book11 layout
   (grouped 3-row header) by `logbook_engine.py`.

## Column mapping (decisions confirmed with the requester)

- **Product Name** = the *handwritten* real product (the folder/product, e.g.
  `ECARE 243`). **Previous Reactor/Line** = the *struck-through printed* product
  (e.g. `ORCA-B`). The engine reads both (`product_name`, `printed_product_struck`).
- **Raw materials** → `LA`, `KOH`, `EO` by name; every other material fills
  `RM-4…RM-12` in order, and its name is kept in a companion **`RM-n Material`**
  column so identity is never lost. Value = *Actual* qty (falls back to Recipe).
- **Process steps** → the 8 start/finish time pairs (Inertization … Unloading).
- **QC analysis** → 5 fixed slots; extra rows overflow into added QC columns.
- **Complete Analysis / Specification** → the 8 Book11 columns
  (App, Meout, Alpha, CP, OH, Free EO, 1,4 Dioxane, pEch) are filled by synonym;
  **any other parameter** (MEA/DEA/TEA, B.Value, Iodine, Free PO, Viscosity, PH…)
  becomes its **own added column** — this is what lets it fit ~1000 products.
- **Remarks** (new column) = the full "Shift Process Activities" narrative from
  the paired remarks page.
- Added provenance columns: Packing/Filling, Total Filled (kg), Tank No., Panel
  Incharge, Form Type, Source Image(s), Pages, Confidence %, Extra Fields.

> Note: the empty `PAR-1…PAR-24` / `deepak` / `Field` columns from the original
> Book11 sample are **not** reproduced (they carried no data and no defined
> meaning). Ask if you want them added back verbatim for drop-in compatibility.

## Using it

Manual mode → **Plant Operations → Log Book** → drop the page photos (one
product's pages, or hundreds across many products) → **Build Register** →
review/edit the table → **Download Log Book Register (Excel)**. Edits in the
review table flow into the downloaded register.

## Accuracy notes

- Handwriting is read by `DEFAULT_MODEL` (`google/gemini-2.5-flash`). For the
  hardest pages, switch `DEFAULT_MODEL=google/gemini-2.5-pro` in `.env`, and use
  the editable review table to correct any field before export.
- Every value is best-effort; nothing is hallucinated (blank → left empty).

## Files

```
processors/logbook/
  manifest.json            # engine=logbook, Plant Operations, production
  schema/schema.json       # one page's extraction shape
  prompts/v1/              # system + extraction prompts (classify + read)
  logbook_engine.py        # per-image extract, assembly, register (headless)
  _offline_test.py         # mock-AI pipeline test (no network)
  README.md
```

Self-tests: `python processors/logbook/_offline_test.py` (offline) and
`run_selftest.bat` / `_live_selftest.py` (imports + discovery + real AI).
