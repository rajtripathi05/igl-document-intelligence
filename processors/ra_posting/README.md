# RA Posting (Marketing)

A **tabular** processor (`"engine": "tabular"` in `manifest.json`) — it does NOT
use the AI/OCR document pipeline. It reads structured **bank statements** and
produces a merged, customer-wise summary of **credit (CR) receipts**.

## Input

Upload one or more bank statements as **Excel (`.xlsx`, `.xlsb`, `.xls`) or CSV**.
`.xlsb` (Excel Binary) needs `pyxlsb` and `.xls` (legacy) needs `xlrd` — both are
in `requirements.txt`. Two formats are auto-detected from their columns:

- **IDBI** — `Srl | Txn Date | Value Date | Description | Cheque No | CR/DR | CCY | Amount (INR) | Balance (INR)`
  (credit = `CR/DR` is `Cr.`)
- **SBI** — `Txn Date | Value Date | Description | Ref No./Cheque No. | Branch Code | Debit | Credit | Balance`
  (credit = the `Credit` column has a value)

Preamble/metadata rows above the table are tolerated — the header row is located
automatically. Multiple files (SBI and/or IDBI) are **merged into one summary**.

## Output

A single Excel workbook with columns:

```
Date | Customer Name | Amount | Document No. | Mode | Bank Name
```

- **Only CR (credit) entries** are included.
- Grouped by **Customer Name, A–Z**, each credit as one row.
- A **`<name> Total`** subtotal row per customer, and a final **`GRAND TOTAL`**.
- **Bank Name** = the source bank (SBI / IDBI), auto-detected.
- **Document No.** = the transaction reference / UTR (SBI: `Ref No./Cheque No.`
  column; IDBI: `Cheque No` if present, else the UTR parsed from the narration).
- **Mode** = NEFT / RTGS / IMPS / UPI / Cheque / Cash, derived from the narration.

## How customer names are derived (Hybrid)

1. **Rule-based (always):** the trailing party segment of the narration
   (after the last `*` or `-`) — e.g. `NEFT-IN42614555284440-JAIN AGRO CHEM`
   → `JAIN AGRO CHEM`.
2. **AI cleanup (when a key is configured):** the shared AI gateway normalises
   the messy narration into a canonical customer name (proper case, no codes/UTR,
   same company → same name). If AI is unavailable the rule-based name is used —
   the summary is always produced.

## Files

- `manifest.json` — metadata; `"engine": "tabular"` routes uploads here.
- `parser.py` — the deterministic engine. Entry point:
  `run(files, ai_gateway=None) -> {columns, rows, excel_bytes, warnings, stats}`.
- `samples/` — example SBI/IDBI statements for testing.

No schema/prompts are needed (this processor performs no AI field-extraction).
To tweak behaviour (e.g. which date column, mode keywords, doc-no source) edit
`parser.py` only.
