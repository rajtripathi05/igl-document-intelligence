"""RA Posting — deterministic tabular engine (hybrid AI name cleanup).

Reads SBI or IDBI bank statements (Excel/CSV), keeps only CREDIT (CR) entries,
and produces a customer-wise merged summary:

    Date | Customer Name | Amount | Document No. | Mode | Bank Name

Customers are grouped A-Z, each credit shown as one row, followed by a
``<name> Total`` subtotal row per customer and a final ``GRAND TOTAL`` row —
matching the business template.

Hybrid design (per the business decision):
- **Deterministic (Python):** bank detection, header location, CR filtering,
  amount/date parsing, payment mode, document number, and a first-pass
  customer-name heuristic — all exact and free.
- **AI (optional):** the shared AI gateway cleans/normalises the messy narration
  into a canonical customer name. If AI is unavailable it degrades gracefully to
  the rule-based name — the summary is always produced.

Bank Name = the SOURCE bank (SBI / IDBI), auto-detected from the file's columns.
Document No. = the transaction reference/UTR (SBI: 'Ref No./Cheque No.' column;
IDBI: 'Cheque No' when present, else the UTR parsed from the narration).

Entry point (called by ``FolderProcessor.run_tabular``):
    run(files: list[tuple[str, bytes]], ai_gateway=None) -> dict
"""

from __future__ import annotations

import io
import json
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

#: Output columns, in order (mirrors the business summary template).
SUMMARY_COLUMNS = ["Date", "Customer Name", "Amount", "Document No.", "Mode", "Bank Name"]

#: Payment-mode word patterns (whole-word, so 'PRODUCTS' never matches 'CTS').
_MODE_WORDS: list[tuple[str, str]] = [
    (r"\bRTGS\b", "RTGS"),
    (r"\bNEFT\b", "NEFT"),
    (r"\bIMPS\b", "IMPS"),
    (r"\bUPI\b", "UPI"),
    (r"\bCHEQUE\b", "Cheque"),
    (r"\bCHQ\b", "Cheque"),
    (r"\bCLG\b", "Cheque"),
    (r"\bCTS\b", "Cheque"),
    (r"\bCASH\b", "Cash"),
]

#: First token of a slash-delimited IMPS/NEFT narration (MODE/ref/NAME/...).
_SLASH_MODES = {"IMPS", "NEFT", "RTGS", "UPI"}

#: Max unique narrations sent to the AI per request (keeps token cost bounded).
_AI_BATCH = 80


# ----- Small parsing helpers -------------------------------------------- #


def _norm(value: Any) -> str:
    """Normalize a header cell for tolerant matching (lowercase alnum only)."""
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _num(value: Any) -> float | None:
    """Parse an Indian-formatted amount ('10,69,870.00', '168,740') to float.

    Returns None for blanks/dashes. Parenthesised values are treated as negative.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "-", "--"):
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^0-9.]", "", text)
    if text in ("", "."):
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def _fmt_date(value: Any, dayfirst: bool) -> str:
    """Normalize a statement date to DD/MM/YYYY (best effort; raw on failure).

    Handles text dates, real datetimes, and Excel serial numbers (which binary
    ``.xlsb`` / legacy ``.xls`` files often yield instead of formatted dates).
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    if not text:
        return ""
    # Excel serial date fallback (days since 1899-12-30), ~1954..2119.
    try:
        serial = float(text)
    except ValueError:
        serial = None
    if serial is not None and 20000 <= serial <= 80000:
        from datetime import timedelta

        return (datetime(1899, 12, 30) + timedelta(days=int(serial))).strftime("%d/%m/%Y")
    text = text.split()[0]  # drop any trailing time component
    day_formats = ("%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y", "%d/%m/%y", "%d-%m-%y")
    month_formats = ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y")
    order = (*day_formats, *month_formats) if dayfirst else (*month_formats, *day_formats)
    for fmt in (*order, "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


def _mode(description: Any) -> str:
    """Derive the payment mode from the narration text.

    Uses whole-word matching first (NEFT/RTGS/IMPS/UPI/Cheque/Cash), then infers
    from a leading bank reference code when no keyword is present — e.g.
    'HDFCR52026...'/'ICICR4...' (4-letter bank + 'R' + digits) -> RTGS,
    '...N...' -> NEFT.
    """
    text = str(description or "").upper()
    for pattern, label in _MODE_WORDS:
        if re.search(pattern, text):
            return label
    match = re.match(r"^([A-Z]{4})([RN])\d", text.strip())
    if match:
        return "RTGS" if match.group(2) == "R" else "NEFT"
    return ""


def _clean_name_tail(value: Any) -> str:
    """Tidy an extracted name: collapse whitespace, strip edge punctuation."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text.strip(" .-*/").strip()


def _heuristic_name(description: Any) -> str:
    """First-pass customer name from a narration (handles the observed formats).

    - 'NEFT-IN42614555284440-JAIN AGRO CHEM'            -> 'JAIN AGRO CHEM'  (dash)
    - '...*AXODH14227614576*VARDHMAN HEALTHC--'          -> 'VARDHMAN HEALTHC' (SBI star)
    - 'IMPS/614414542545/YASHIKA PR/BANK NO/XX0000/...'  -> 'YASHIKA PR'      (slash)
    - 'HDFCR52026052261673880 NAV UDYOG'                 -> 'NAV UDYOG'       (ref + name)

    Rule-based only — a best-effort fallback; the AI cleanup refines these from
    the full narration when a key is configured.
    """
    text = str(description or "").strip()
    if not text:
        return ""
    # MODE/ref/NAME/... (IMPS retail narration): the name is the 3rd field.
    if "/" in text:
        parts = [p.strip() for p in text.split("/")]
        if len(parts) >= 3 and parts[0].upper() in _SLASH_MODES:
            name = _clean_name_tail(parts[2])
            if name:
                return name
    # *-delimited (SBI): trailing party segment.
    if "*" in text:
        return _clean_name_tail(text.split("*")[-1])
    # Leading bank-reference token (has a digit, 10+ chars) then the name.
    match = re.match(r"^(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{10,}\s+(.+)$", text)
    if match:
        return _clean_name_tail(match.group(1))
    # -delimited (NEFT-ref-NAME): trailing segment.
    if "-" in text:
        return _clean_name_tail(text.split("-")[-1])
    return _clean_name_tail(text)


def _utr_from_desc(description: Any) -> str:
    """Extract the first long alphanumeric token (UTR-like) from a narration."""
    tokens = re.findall(r"[A-Z0-9]{10,}", str(description or "").upper())
    return tokens[0] if tokens else ""


def _idbi_docno(cheque_no: str, description: str) -> str:
    """IDBI document number: cheque number if present, else the UTR from narration."""
    cheque = (cheque_no or "").strip()
    if cheque and cheque not in ("0", "0.0"):
        return cheque
    match = re.search(r"(?:NEFT|RTGS|IMPS|UPI)[-\s]*([A-Z0-9]{6,})", str(description).upper())
    if match:
        return match.group(1)
    return _utr_from_desc(description)


def _sbi_docno(ref: str, description: str) -> str:
    """SBI document number: the 'Ref No./Cheque No.' column, else UTR from narration."""
    text = (ref or "").strip().rstrip("/ ").strip()
    return text or _utr_from_desc(description)


# ----- Table reading + bank detection ----------------------------------- #


def _read_table(name: str, data: bytes):
    """Read an uploaded Excel/CSV file into a header-less string DataFrame.

    CSVs are parsed row-by-row and padded to a uniform width so that a short
    preamble line (fewer commas than the table) cannot collapse the column count
    or cause data rows to be dropped as "bad lines".
    """
    import pandas as pd

    lower = name.lower()
    if lower.endswith(".csv"):
        import csv as _csv

        text = data.decode("utf-8-sig", errors="replace")
        rows = list(_csv.reader(io.StringIO(text)))
        width = max((len(r) for r in rows), default=0)
        rows = [r + [""] * (width - len(r)) for r in rows]
        frame = pd.DataFrame(rows, dtype=str)
    else:
        # Pick the reader engine by format: .xlsb (binary) -> pyxlsb,
        # .xls (legacy) -> xlrd, .xlsx -> openpyxl (auto).
        if lower.endswith(".xlsb"):
            engine = "pyxlsb"
        elif lower.endswith(".xls"):
            engine = "xlrd"
        else:
            engine = None
        frame = pd.read_excel(io.BytesIO(data), header=None, dtype=str, engine=engine)
    return frame.fillna("")


def _find_header(frame) -> tuple[int | None, str | None, list[str]]:
    """Locate the header row and detect the bank (SBI vs IDBI).

    Returns ``(row_index, bank, normalized_header_cells)`` or ``(None, None, [])``.
    """
    limit = min(len(frame), 40)
    for i in range(limit):
        cells = [_norm(x) for x in frame.iloc[i].tolist()]
        cellset = {c for c in cells if c}
        if "debit" in cellset and "credit" in cellset:
            return i, "SBI", cells
        if "crdr" in cellset and any(c.startswith("amount") for c in cells):
            return i, "IDBI", cells
    return None, None, []


def _cell(row: list, colmap: dict[str, int], key: str | None) -> str:
    """Return the trimmed string cell for a normalized column key."""
    if key is None:
        return ""
    pos = colmap.get(key)
    if pos is None or pos >= len(row):
        return ""
    return str(row[pos]).strip()


def _row_idbi(row: list, colmap: dict[str, int]) -> dict[str, Any] | None:
    """Parse one IDBI data row into a credit transaction (or None if not a credit)."""
    if _norm(_cell(row, colmap, "crdr")) != "cr":
        return None
    amount_key = next((k for k in colmap if k.startswith("amount")), None)
    amount = _num(_cell(row, colmap, amount_key))
    if amount is None or amount == 0:
        return None
    description = _cell(row, colmap, "description")
    return {
        "date": _fmt_date(_cell(row, colmap, "txndate"), dayfirst=True),
        "description": description,
        "amount": amount,
        "doc_no": _idbi_docno(_cell(row, colmap, "chequeno"), description),
        "mode": _mode(description),
        "bank": "IDBI",
        "name_raw": _heuristic_name(description),
    }


def _row_sbi(row: list, colmap: dict[str, int]) -> dict[str, Any] | None:
    """Parse one SBI data row into a credit transaction (or None if not a credit)."""
    credit = _num(_cell(row, colmap, "credit"))
    if credit is None or credit == 0:
        return None
    description = _cell(row, colmap, "description")
    ref_key = next((k for k in colmap if "refno" in k or k == "chequeno"), None)
    return {
        "date": _fmt_date(_cell(row, colmap, "txndate"), dayfirst=False),
        "description": description,
        "amount": credit,
        "doc_no": _sbi_docno(_cell(row, colmap, ref_key), description),
        "mode": _mode(description),
        "bank": "SBI",
        "name_raw": _heuristic_name(description),
    }


def _parse_file(name: str, data: bytes) -> tuple[list[dict[str, Any]], str | None]:
    """Parse a single file into its list of credit transactions + detected bank."""
    frame = _read_table(name, data)
    header_index, bank, header_cells = _find_header(frame)
    if header_index is None:
        return [], None

    colmap: dict[str, int] = {}
    for pos, cell in enumerate(header_cells):
        if cell and cell not in colmap:  # first occurrence wins
            colmap[cell] = pos

    parse_row = _row_idbi if bank == "IDBI" else _row_sbi
    transactions: list[dict[str, Any]] = []
    for r in range(header_index + 1, len(frame)):
        row = frame.iloc[r].tolist()
        if all(str(x).strip() == "" for x in row):
            continue
        txn = parse_row(row, colmap)
        if txn:
            transactions.append(txn)
    return transactions, bank


# ----- Hybrid AI name cleanup ------------------------------------------- #

_AI_SYSTEM = (
    "You normalise the paying customer/company name from Indian bank statement "
    "transaction narrations. Return ONLY strict JSON. Never invent a name that is "
    "not present in the narration."
)


def _clean_names_ai(transactions: list[dict[str, Any]], ai_gateway) -> dict[str, str]:
    """Return a mapping ``narration -> clean customer name`` using the AI gateway.

    Deduplicates by narration and processes in bounded batches. Raises on gateway
    failure so the caller can fall back to the rule-based names.
    """
    unique: dict[str, str] = {}
    for txn in transactions:
        unique.setdefault(txn["description"], txn["name_raw"])
    items = list(unique.items())

    mapping: dict[str, str] = {}
    for start in range(0, len(items), _AI_BATCH):
        batch = items[start : start + _AI_BATCH]
        payload = [
            {"i": i, "narration": desc, "guess": guess}
            for i, (desc, guess) in enumerate(batch)
        ]
        instruction = (
            "For each item, extract the clean paying customer/party name from the "
            "bank narration. Rules: proper Title Case; drop bank/branch codes, "
            "IFSC, UTR/reference numbers, NEFT/RTGS/IMPS/UPI words, 'BY TRANSFER', "
            "batch/lot numbers and trailing dashes. If two items clearly name the "
            "same company, return the SAME canonical name for both. If unclear, "
            "return your best name from the narration (you may use 'guess').\n"
            "Respond as JSON exactly: {\"results\":[{\"i\":0,\"name\":\"...\"}]}\n"
            f"Items: {json.dumps(payload, ensure_ascii=False)}"
        )
        response = ai_gateway.extract(
            system_prompt=_AI_SYSTEM,
            instruction=instruction,
            parts=[],
            json_mode=True,
        )
        data = json.loads(response.text)
        for entry in data.get("results", []):
            idx = entry.get("i")
            name = str(entry.get("name") or "").strip()
            if isinstance(idx, int) and 0 <= idx < len(batch) and name:
                mapping[batch[idx][0]] = name
    return mapping


# ----- Summary assembly + Excel ----------------------------------------- #


def _build_rows(transactions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float, int]:
    """Group by customer (A-Z), emit detail + subtotal rows + a grand total."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for txn in transactions:
        name = txn.get("clean_name") or txn.get("name_raw") or "(Unknown)"
        groups.setdefault(name, []).append(txn)

    rows: list[dict[str, Any]] = []
    grand_total = 0.0
    for name in sorted(groups, key=lambda s: s.lower()):
        subtotal = 0.0
        for txn in groups[name]:
            amount = float(txn.get("amount") or 0.0)
            subtotal += amount
            rows.append({
                "Date": txn.get("date", ""),
                "Customer Name": name,
                "Amount": round(amount, 2),
                "Document No.": txn.get("doc_no", ""),
                "Mode": txn.get("mode", ""),
                "Bank Name": txn.get("bank", ""),
            })
        rows.append({
            "Date": "", "Customer Name": f"{name} Total", "Amount": round(subtotal, 2),
            "Document No.": "", "Mode": "", "Bank Name": "",
        })
        grand_total += subtotal

    if groups:
        rows.append({
            "Date": "", "Customer Name": "GRAND TOTAL", "Amount": round(grand_total, 2),
            "Document No.": "", "Mode": "", "Bank Name": "",
        })
    return rows, round(grand_total, 2), len(groups)


def _is_total_row(row: dict[str, Any]) -> bool:
    """True for subtotal / grand-total rows (styled bold, no per-txn fields)."""
    name = str(row.get("Customer Name", ""))
    return name == "GRAND TOTAL" or name.endswith(" Total")


def build_summary_excel(rows: list[dict[str, Any]]) -> bytes:
    """Render the customer summary to a styled single-sheet workbook."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    total_font = Font(bold=True)
    grand_fill = PatternFill("solid", fgColor="DDEBF7")
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Customer Summary"

    for col, header in enumerate(SUMMARY_COLUMNS, start=1):
        cell = sheet.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border

    for r, row in enumerate(rows, start=2):
        is_total = _is_total_row(row)
        is_grand = str(row.get("Customer Name", "")) == "GRAND TOTAL"
        for col, header in enumerate(SUMMARY_COLUMNS, start=1):
            cell = sheet.cell(row=r, column=col, value=row.get(header))
            cell.border = border
            if header == "Amount" and isinstance(row.get(header), (int, float)):
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right")
            if is_total:
                cell.font = total_font
            if is_grand:
                cell.fill = grand_fill

    widths = {"Date": 12, "Customer Name": 34, "Amount": 16,
              "Document No.": 22, "Mode": 10, "Bank Name": 12}
    from openpyxl.utils import get_column_letter
    for col, header in enumerate(SUMMARY_COLUMNS, start=1):
        sheet.column_dimensions[get_column_letter(col)].width = widths.get(header, 14)
    sheet.freeze_panes = "A2"

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ----- Entry point ------------------------------------------------------- #


def run(files: list[tuple[str, bytes]], ai_gateway=None) -> dict[str, Any]:
    """Parse the uploaded statements and build the merged customer summary.

    Args:
        files: ``(filename, raw_bytes)`` for each uploaded Excel/CSV statement.
        ai_gateway: Optional shared AI gateway for hybrid customer-name cleanup.

    Returns:
        ``{columns, rows, excel_bytes, warnings, stats}``.
    """
    warnings: list[str] = []
    transactions: list[dict[str, Any]] = []
    banks_seen: list[str] = []

    for name, data in files:
        try:
            file_txns, bank = _parse_file(name, data)
        except Exception as exc:  # noqa: BLE001 - one bad file must not abort the batch
            logger.exception("Failed parsing %s", name)
            warnings.append(f"{name}: could not read file ({exc}).")
            continue
        if bank is None:
            warnings.append(
                f"{name}: unrecognised format — expected SBI (Debit/Credit columns) "
                "or IDBI (CR/DR + Amount columns). Skipped."
            )
            continue
        banks_seen.append(bank)
        if not file_txns:
            warnings.append(f"{name}: no credit (CR) entries found in this {bank} statement.")
        transactions.extend(file_txns)

    ai_used = False
    if transactions:
        mapping: dict[str, str] = {}
        has_capacity = bool(ai_gateway is not None and getattr(ai_gateway, "has_capacity", lambda: False)())
        if has_capacity:
            try:
                mapping = _clean_names_ai(transactions, ai_gateway)
                ai_used = bool(mapping)
            except Exception as exc:  # noqa: BLE001 - degrade to heuristic names
                logger.warning("AI name cleanup failed: %s", exc)
                warnings.append(f"AI name cleanup unavailable — used rule-based names. ({exc})")
        for txn in transactions:
            txn["clean_name"] = mapping.get(txn["description"]) or txn["name_raw"] or "(Unknown)"

    rows, grand_total, customers = _build_rows(transactions)

    stats = {
        "files": len(files),
        "credit_entries": len(transactions),
        "customers": customers,
        "total_amount": grand_total,
        "banks": sorted(set(banks_seen)),
        "ai_used": ai_used,
    }

    return {
        "columns": SUMMARY_COLUMNS,
        "rows": rows,
        "excel_bytes": build_summary_excel(rows),
        "warnings": warnings,
        "stats": stats,
    }
