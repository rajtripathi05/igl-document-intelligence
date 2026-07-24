# Sales Order (Marketing) — v2, SO-Step extraction + ZCUSTMst master fallback

Processes **customer purchase orders** (POs issued BY customers TO India
Glycols) into SAP-ready Sales Order data. Replaces the old generic
purchase-order extraction ("delete the old process and continue with this
one") — the schema, prompts (v2), validator and register are all built around
the business **SO Step** sheet.

## What it extracts (SO Step fields)

Sold/Bill to party · Ship to party · Customer reference/PO No. · Cust. Ref./PO
date · Payment term · Incoterm (+ location, 2nd location) · Material code with
packaging type · Plant · Qty. · Unit · Industry key · Test report required ·
Insurance · Basis of delivery · Price · Discount/credit note ·
Schedule/dispatch date · ETA date — plus the customer/ship-to/supplier GSTIN
blocks, line items and totals.

`plant` / `industry_key` are SAP-side values: extracted only when literally
printed, otherwise left for the reviewer.

## Customer-master fallback (ZCUSTMst)

`validator.py` matches the extracted customer against **`master/ZCUSTMst.xls`**:

1. **GSTIN** — exact 15-character match (confidence 98).
2. **PAN** — same PAN inside a different state GSTIN (flags the state issue).
3. **Name** — normalised/fuzzy match (PVT/LTD etc. ignored), address PIN/city
   as tie-breaker.

On a match the **Sold/Bill to party is filled from the master**
(`NAME [customer code]`) and every PO-vs-master difference (name, GSTIN, PIN)
is reported to the reviewer. No match -> the document is flagged
"Customer not found in ZCUSTMst" — nothing is invented.

**To update the master:** replace `master/ZCUSTMst.xls` with a fresh SAP
export (the file may be real `.xls` or `.xlsx` — both work; the header row is
found automatically). It is re-read whenever the file changes. The current
file is a 15-customer sample, so most sample POs show "not matched" until the
full dump is dropped in.

## Output — one row per uploaded PO

The consolidated register (`Sales Orders` sheet) has the SO-Step columns in
business order plus `Customer Code (master)`, `Master Match`,
`Customer GSTIN (PO)`, `Master GSTIN`, `Grand Total`, `Source File`.
Multiple uploaded files append **one row each, one after another**.
Per-document workbooks use the generic spec-driven exporter.

## Files

- `manifest.json` — sections (review UI), line items, register mapping (v2).
- `schema/schema.json` — SO JSON schema (single source of truth).
- `prompts/v2/` — system + extraction prompts (customer-PO aware: never
  reports India Glycols as the customer; separates customer / ship-to /
  supplier GSTINs).
- `validator.py` — validation + auto-fix + ZCUSTMst matching + the flat
  register fields (material_with_packaging, total_quantity, unit,
  price_summary, sold_to/ship_to party).
- `master/ZCUSTMst.xls` — the customer master (replace to refresh).
- `samples/` — real customer POs for testing.
