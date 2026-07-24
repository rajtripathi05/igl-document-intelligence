# RA Posting (Marketing) — v2

A **tabular** processor (`"engine": "tabular"` in `manifest.json`) — it does NOT
use the AI/OCR document pipeline. It reads structured **bank statements** and
produces a customer-wise summary of **credit (CR) receipts only**.

## Input

Upload one or more bank statements as **Excel (`.xlsx`, `.xlsb`, `.xls`) or CSV**.
`.xlsb` (Excel Binary) needs `pyxlsb` and `.xls` (legacy) needs `xlrd` — both are
in `requirements.txt`. Two formats are auto-detected from their columns:

- **IDBI** — `Srl | Txn Date | Value Date | Description | Cheque No | CR/DR | CCY | Amount (INR) | Balance (INR)`
  (credit = `CR/DR` is `Cr.`)
- **SBI** — `Txn Date | Value Date | Description | Ref No./Cheque No. | Branch Code | Debit | Credit | Balance`
  (credit = the `Credit` column has a value)

### v2 handles the real-world compiled workbooks

- **Every sheet of every workbook is read** (compiled files keep one bank per
  sheet, e.g. an 'IDBI' sheet and an 'SBI' sheet).
- **Many statement blocks per sheet** — the same account downloaded repeatedly
  and pasted below the previous download, each block with its own header row
  and an overlapping date range. Every header is detected and columns are
  re-mapped per block.
- **De-duplication** — the same transaction downloaded twice is kept once.
  Identity = canonical timestamp + narration + reference + amount. The running
  balance is deliberately NOT part of the identity (a retroactive posting
  shifts all later balances between two downloads). Genuine repeat payments
  differ in timestamp or reference, so they are kept.

## Output

One Excel workbook, **one sheet per bank** (`IDBI`, `SBI`, …) plus a combined
**`All Banks`** sheet when several banks are present. Each sheet:

```
we will refer CR entries only
summary of customers
Date | Customer Name | Amount | Document No. | Mode | Bank Name
```

- **Only CR (credit) entries** are included.
- Grouped by **Customer Name, A-Z**, each credit as one row, sorted by date.
- A **`<name> Total`** subtotal row per customer, and a final **`GRAND TOTAL`**.
- **Bank Name** = the source bank, from the sheet name ('IDBI'/'SBI'), the
  column signature, or the file name.
- **Document No.** = cheque number > UTR from the narration ('RTGS UTR NO:',
  'NEFT-<utr>-', '*<utr>*', 'Chq <num>', IMPS reference) > reference-column token.
- **Mode** = NEFT / RTGS / IMPS / UPI / Cheque / Cash / INB / Bill-LC, derived
  from the narration (including leading bank-reference codes like `HDFCR5…`).

## How customer names are derived (Hybrid)

1. **Rule-based (always):** format-aware extraction from the narration —
   - `NEFT-IN42614555284440-JAIN AGRO CHEM` → `JAIN AGRO CHEM`
   - `HDFCR52026052461944310 GOYAL TRADING COMPANY` → `GOYAL TRADING COMPANY`
   - `IMPS/6144…/YASHIKA PR/…` and `UPI/CR/6128…/SUDHAKAR/…` → 3rd/4th field
   - SBI `BY TRANSFER-RTGS UTR NO: …--TAPASHI PHARMA…` → after the `--`
   - SBI `NEFT*IFSC*UTR*NAME*remark--` → the segment AFTER the UTR
   - SBI ref column `TRANSFER FROM <acct> / <NAME>` (or `<NAME> /`) → the name
   - Truncated variants of the same customer are merged
     (`ASHTA LAKS` → `ASHTA LAKSHMI ENTERPRISES`).
   - Name-less credits (LC/BD bill realisations, cheque deposits, internal
     transfers) group under **`(Unknown)`** for reviewer attention.
2. **AI cleanup (when a key is configured):** the shared AI gateway normalises
   the messy narration into a canonical customer name (proper case, no codes/UTR,
   same company → same name). If AI is unavailable the rule-based name is used —
   the summary is always produced.

## Files

- `manifest.json` — metadata; `"engine": "tabular"` routes uploads here.
- `parser.py` — the deterministic engine. Entry point:
  `run(files, ai_gateway=None) -> {columns, rows, excel_bytes, warnings, stats}`.
- `samples/` — example statements for testing
  (`Ra posting samples/suman bank statements (1).xlsb` is the reference case:
  3,668 raw credit rows → 851 unique credits after de-duplication).

No schema/prompts are needed (this processor performs no AI field-extraction).
To tweak behaviour (e.g. mode keywords, doc-no source, name rules) edit
`parser.py` only.
