"""Sales Order validator + auto-fix with ZCUSTMst customer-master matching.

The Sales Order process (customer POs -> SAP SO) falls back on the customer
master ``ZCUSTMst.xls`` as the single source of truth for WHO the customer is:

- The extracted customer (PO issuer) is matched against the master by
  **GSTIN first** (exact 15-char match), then **PAN** (characters 3-12 of the
  GSTIN, catching a different state registration of the same company), then
  **normalised / fuzzy name**, with the address (PIN code, city) as a
  tie-breaker and cross-check.
- On a match, the SO "Sold/Bill to party" is FILLED FROM THE MASTER
  (canonical name + customer code) and every disagreement between the PO and
  the master (name spelling, GSTIN, address) is reported as an issue for the
  reviewer — the master is the reference, the PO is the evidence.
- No match -> the document is flagged: the customer must be created in SAP or
  the master refreshed. Nothing is invented.

The master file is looked up in (first hit wins):
    processors/purchase_order/master/ZCUSTMst.xls(x)
    <app root>/masters/ZCUSTMst.xls(x)
    processors/purchase_order/samples/ZCUSTMst.xls(x)
Despite the ``.xls`` name the business file is often a real ``.xlsx`` — both
are handled. Replace the file to update the master; it is re-read when its
modification time changes.

Also fills the flat SO-Step convenience fields used by the Excel register
(one row per uploaded PO): sold_to_party, ship_to_party,
material_with_packaging, total_quantity, unit, price_summary — and normalises
dates (ISO) and numbers like the generic auto-fix.

Contract (see ``FolderProcessor``):
    validate(data) -> list[str]
    auto_fix(data) -> (data, notes)   # notes: {field, old, new, reason, confidence}
"""

from __future__ import annotations

import difflib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_FOLDER = Path(__file__).resolve().parent

#: Candidate master-file locations, first existing file wins.
_MASTER_CANDIDATES = (
    _FOLDER / "master" / "ZCUSTMst.xlsx",
    _FOLDER / "master" / "ZCUSTMst.xls",
    _FOLDER.parent.parent / "masters" / "ZCUSTMst.xlsx",
    _FOLDER.parent.parent / "masters" / "ZCUSTMst.xls",
    _FOLDER / "samples" / "ZCUSTMst.xlsx",
    _FOLDER / "samples" / "ZCUSTMst.xls",
)

_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$", re.IGNORECASE)
_PIN_RE = re.compile(r"\b(\d{6})\b")

_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y",
    "%d.%m.%y", "%d-%b-%Y", "%d-%b-%y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d",
)

#: Company-form words dropped when normalising names for comparison.
_NAME_NOISE = (
    "PRIVATE", "PVT", "LIMITED", "LTD", "LLP", "COMPANY", "CO", "INDIA",
    "INDUSTRIES", "INDUSTRIAL", "ENTERPRISES", "CORPORATION", "CORP", "THE",
)


# ----- Small helpers ------------------------------------------------------ #


def _get(data: dict, path: str) -> Any:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _set(data: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _note(field: str, old: Any, new: Any, reason: str, confidence: int) -> dict[str, Any]:
    return {"field": field, "old": old, "new": new, "reason": reason, "confidence": confidence}


def _iso_date(value: Any) -> str | None:
    """ISO date for a recognizable printed date, else None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", text)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9.\-]", "", str(value))
    if text in ("", "-", "."):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _clean_gstin(value: Any) -> str:
    return re.sub(r"[^0-9A-Z]", "", str(value or "").upper())


def _norm_name(value: Any) -> str:
    """Normalise a company name for comparison (upper, no punctuation/noise)."""
    text = re.sub(r"[^A-Z0-9 ]", " ", str(value or "").upper())
    words = [w for w in text.split() if w and w not in _NAME_NOISE]
    return " ".join(words)


def _name_similarity(a: str, b: str) -> float:
    """Similarity of two normalised names (0..1, prefix-aware)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    compact_a, compact_b = a.replace(" ", ""), b.replace(" ", "")
    if len(compact_a) >= 8 and (compact_b.startswith(compact_a) or compact_a.startswith(compact_b)):
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


# ----- Customer master (ZCUSTMst) ---------------------------------------- #

_MASTER_CACHE: dict[str, tuple[float, list[dict[str, str]]]] = {}


def _master_path() -> Path | None:
    for candidate in _MASTER_CANDIDATES:
        if candidate.is_file():
            return candidate
    return None


def _read_master(path: Path) -> list[dict[str, str]]:
    """Read ZCUSTMst into records, tolerant of layout and of xlsx-named-xls."""
    import pandas as pd

    frame = None
    for engine in (None, "openpyxl", "xlrd"):
        try:
            frame = pd.read_excel(path, header=None, dtype=str, engine=engine)
            break
        except Exception:  # noqa: BLE001 - try the next engine
            continue
    if frame is None:
        raise RuntimeError(f"Could not read customer master: {path.name}")
    frame = frame.fillna("")

    def norm(cell: Any) -> str:
        return re.sub(r"[^a-z0-9]", "", str(cell).lower())

    header_row = None
    for i in range(min(len(frame), 15)):
        cells = [norm(c) for c in frame.iloc[i].tolist()]
        if "customercode" in cells and "customername" in cells:
            header_row = i
            break
    if header_row is None:
        raise RuntimeError(f"Customer master {path.name}: header row not found.")

    headers = [norm(c) for c in frame.iloc[header_row].tolist()]

    def col(*names: str) -> int | None:
        for name in names:
            if name in headers:
                return headers.index(name)
        return None

    c_code = col("customercode")
    c_name = col("customername")
    c_gstin = col("customergstinno", "gstin", "customergstin")
    c_addr = col("address")
    c_city = col("city")
    c_postal = col("postalcode", "pincode")
    c_region = col("gstinregiondesc", "region", "state")
    addr_parts = [i for i, h in enumerate(headers)
                  if h in ("houseno", "street", "street2", "street3", "street4", "street5")]

    records: list[dict[str, str]] = []
    for r in range(header_row + 1, len(frame)):
        row = [str(x).strip() for x in frame.iloc[r].tolist()]
        code = row[c_code] if c_code is not None and c_code < len(row) else ""
        name = row[c_name] if c_name is not None and c_name < len(row) else ""
        if not code and not name:
            continue
        if c_addr is not None and c_addr < len(row) and row[c_addr]:
            address = row[c_addr]
        else:
            address = ", ".join(row[i] for i in addr_parts if i < len(row) and row[i])
            tail = [row[i] for i in (c_city, c_postal, c_region)
                    if i is not None and i < len(row) and row[i]]
            address = ", ".join(filter(None, [address, *tail]))
        records.append({
            "code": code,
            "name": name,
            "norm_name": _norm_name(name),
            "gstin": _clean_gstin(row[c_gstin]) if c_gstin is not None and c_gstin < len(row) else "",
            "address": address,
            "city": (row[c_city] if c_city is not None and c_city < len(row) else "").upper(),
            "postal": row[c_postal] if c_postal is not None and c_postal < len(row) else "",
        })
    return records


def load_master() -> list[dict[str, str]]:
    """Return the customer-master records (cached until the file changes)."""
    path = _master_path()
    if path is None:
        return []
    key = str(path)
    mtime = path.stat().st_mtime
    cached = _MASTER_CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    records = _read_master(path)
    _MASTER_CACHE[key] = (mtime, records)
    logger.info("Loaded customer master %s: %d customers.", path.name, len(records))
    return records


def match_customer(
    name: Any, gstin: Any, address: Any, records: list[dict[str, str]]
) -> tuple[dict[str, str] | None, str, list[str]]:
    """Match an extracted customer against the master.

    Returns ``(record | None, method, issues)`` where method is one of
    ``GSTIN`` / ``PAN`` / ``NAME`` / ``NAME+ADDRESS`` / ``""``.
    """
    issues: list[str] = []
    gstin_clean = _clean_gstin(gstin)
    norm = _norm_name(name)
    pin_match = _PIN_RE.search(str(address or ""))
    pin = pin_match.group(1) if pin_match else ""
    addr_upper = str(address or "").upper()

    # 1) Exact GSTIN.
    if gstin_clean and _GSTIN_RE.match(gstin_clean):
        for rec in records:
            if rec["gstin"] and rec["gstin"] == gstin_clean:
                similarity = _name_similarity(norm, rec["norm_name"])
                if similarity < 0.5:
                    issues.append(
                        f"GSTIN {gstin_clean} matches master customer {rec['code']} "
                        f"'{rec['name']}' but the PO shows '{name}' — verify."
                    )
                return rec, "GSTIN", issues

        # 2) Same PAN, different state registration.
        pan = gstin_clean[2:12]
        pan_hits = [rec for rec in records if rec["gstin"] and rec["gstin"][2:12] == pan]
        if len(pan_hits) == 1:
            rec = pan_hits[0]
            issues.append(
                f"PO GSTIN {gstin_clean} is a different STATE registration of master "
                f"customer {rec['code']} '{rec['name']}' (master GSTIN {rec['gstin']}) — "
                "confirm the correct sold-to code for this state."
            )
            return rec, "PAN", issues

    # 3) Name (exact normalised, then fuzzy), address as tie-breaker.
    if norm:
        scored: list[tuple[float, dict[str, str]]] = []
        for rec in records:
            similarity = _name_similarity(norm, rec["norm_name"])
            if similarity >= 0.86:
                scored.append((similarity, rec))
        if scored:
            scored.sort(key=lambda pair: pair[0], reverse=True)
            top_score = scored[0][0]
            top = [rec for score, rec in scored if score >= top_score - 0.02]
            method = "NAME"
            if len(top) > 1:
                narrowed = [rec for rec in top
                            if (pin and rec["postal"] == pin)
                            or (rec["city"] and rec["city"] in addr_upper)]
                if len(narrowed) == 1:
                    top = narrowed
                    method = "NAME+ADDRESS"
                else:
                    issues.append(
                        "Multiple master customers share this name — picked "
                        f"{top[0]['code']} '{top[0]['name']}'; verify the sold-to code."
                    )
            rec = top[0]
            if gstin_clean and rec["gstin"] and rec["gstin"] != gstin_clean:
                issues.append(
                    f"Name matches master customer {rec['code']} '{rec['name']}' but "
                    f"GSTIN differs (PO: {gstin_clean}, master: {rec['gstin']}) — verify."
                )
            if pin and rec["postal"] and rec["postal"] != pin:
                issues.append(
                    f"PIN code differs (PO address: {pin}, master: {rec['postal']}) — "
                    "possible different site of the same customer."
                )
            return rec, method, issues

    return None, "", issues


# ----- Auto-fix ----------------------------------------------------------- #

_DATE_FIELDS = (
    ("sales_order.customer_po_date", "Cust. Ref./PO date"),
    ("sales_order.schedule_dispatch_date", "Schedule/dispatch date"),
    ("sales_order.eta_date", "ETA date"),
)

_ITEM_NUMBER_KEYS = ("quantity", "unit_price", "taxable_amount",
                     "gst_percent", "gst_amount", "total_amount")


def auto_fix(data: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Deterministic fixes + customer-master fallback for the SO fields."""
    notes: list[dict[str, Any]] = []

    # --- 1. Dates -> ISO, numbers -> floats (like the generic auto-fix). ---
    for path, label in _DATE_FIELDS:
        old = _get(data, path)
        fixed = _iso_date(old)
        if fixed and fixed != old:
            _set(data, path, fixed)
            notes.append(_note(label, old, fixed, "Date normalized to ISO format", 97))

    items = data.get("items") or []
    if isinstance(items, list):
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            for key in _ITEM_NUMBER_KEYS:
                old = item.get(key)
                if old in (None, ""):
                    continue
                fixed_num = _number(old)
                if fixed_num is not None and fixed_num != old:
                    item[key] = fixed_num
                    notes.append(_note(f"Item {index} · {key}", old, fixed_num,
                                       "Number cleaned", 96))
            date_old = item.get("delivery_date")
            date_fixed = _iso_date(date_old)
            if date_fixed and date_fixed != date_old:
                item["delivery_date"] = date_fixed
                notes.append(_note(f"Item {index} · delivery_date", date_old, date_fixed,
                                   "Date normalized to ISO format", 97))

    # --- 2. Customer-master fallback (ZCUSTMst). ---------------------------
    customer = data.get("customer") or {}
    name = customer.get("name") or customer.get("bill_to_name")
    gstin = customer.get("gstin") or customer.get("bill_to_gstin")
    address = customer.get("address") or customer.get("bill_to_address")

    match_block = {
        "matched": False, "method": "", "customer_code": "",
        "customer_name": "", "gstin": "", "address": "", "issues": [],
    }
    try:
        records = load_master()
    except Exception as exc:  # noqa: BLE001 - master problems must not kill processing
        logger.warning("Customer master unavailable: %s", exc)
        records = []
        match_block["issues"].append(f"Customer master could not be read ({exc}).")

    if records:
        record, method, issues = match_customer(name, gstin, address, records)
        match_block["issues"].extend(issues)
        if record:
            match_block.update({
                "matched": True,
                "method": method,
                "customer_code": record["code"],
                "customer_name": record["name"],
                "gstin": record["gstin"],
                "address": record["address"],
            })
            confidence = {"GSTIN": 98, "PAN": 90, "NAME": 88, "NAME+ADDRESS": 90}.get(method, 80)
            sold_to = f"{record['name']} [{record['code']}]"
            old_sold = _get(data, "sales_order.sold_to_party") or name
            _set(data, "sales_order.sold_to_party", sold_to)
            if old_sold != sold_to:
                notes.append(_note(
                    "Sold/Bill to party", old_sold, sold_to,
                    f"Filled from customer master ZCUSTMst (matched by {method})",
                    confidence,
                ))
        else:
            match_block["issues"].append(
                "Customer not found in ZCUSTMst master — verify the customer or "
                "update the master file."
            )
    elif not match_block["issues"]:
        match_block["issues"].append("Customer master file not found (ZCUSTMst).")

    if not _get(data, "sales_order.sold_to_party"):
        _set(data, "sales_order.sold_to_party", name or "")
    data["master_match"] = match_block

    # --- 3. Flat SO-Step register fields. ----------------------------------
    ship = data.get("ship_to") or {}
    if not _get(data, "sales_order.ship_to_party"):
        ship_text = ", ".join(filter(None, [str(ship.get("name") or "").strip(),
                                            str(ship.get("address") or "").strip()]))
        _set(data, "sales_order.ship_to_party", ship_text)

    per_item: list[str] = []
    quantities: list[float] = []
    units: list[str] = []
    prices: list[str] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        material = str(item.get("material_code") or "").strip()
        description = str(item.get("description") or "").strip()
        packaging = str(item.get("packaging_type") or "").strip()
        parts = [material]
        if description and description.upper() != material.upper():
            parts.append(description)
        if packaging:
            parts.append(packaging)
        text = " | ".join(p for p in parts if p)
        item["material_with_packaging"] = text
        if text and text not in per_item:
            per_item.append(text)
        quantity = _number(item.get("quantity"))
        if quantity is not None:
            quantities.append(quantity)
        unit = str(item.get("unit") or "").strip()
        if unit and unit not in units:
            units.append(unit)
        price = _number(item.get("unit_price"))
        if price is not None:
            per = str(item.get("price_per") or unit or "").strip()
            price_text = f"{price:g}" + (f"/{per}" if per else "")
            if price_text not in prices:
                prices.append(price_text)

    _set(data, "sales_order.material_with_packaging", "; ".join(per_item))
    _set(data, "sales_order.unit", ", ".join(units))
    _set(data, "sales_order.total_quantity",
         round(sum(quantities), 3) if quantities and len(units) <= 1 else None)
    _set(data, "sales_order.price_summary", "; ".join(prices))

    # --- 4. Normalise test-report flag. -------------------------------------
    flag = _get(data, "sales_order.test_report_required")
    if flag not in (None, ""):
        text = str(flag).strip().upper()
        normalized = "Yes" if text in ("YES", "Y", "TRUE", "REQUIRED", "1") else \
                     "No" if text in ("NO", "N", "FALSE", "NOT REQUIRED", "0") else str(flag)
        if normalized != flag:
            _set(data, "sales_order.test_report_required", normalized)
            notes.append(_note("Test report required", flag, normalized,
                               "Normalized to Yes/No", 95))

    validation = data.setdefault("validation", {})
    validation["line_item_count"] = len(items) if isinstance(items, list) else 0

    return data, notes


# ----- Validation ---------------------------------------------------------- #


def validate(data: dict[str, Any]) -> list[str]:
    """Business validation for SO creation; returns human-readable problems."""
    problems: list[str] = []

    if not _get(data, "sales_order.customer_po_number"):
        problems.append("Customer PO number is missing.")
    if not _get(data, "sales_order.customer_po_date"):
        problems.append("Customer PO date is missing.")
    elif _iso_date(_get(data, "sales_order.customer_po_date")) is None:
        problems.append("Customer PO date is not a recognizable date.")

    customer = data.get("customer") or {}
    if not (customer.get("name") or customer.get("bill_to_name")):
        problems.append("Customer (Sold-to party) name is missing.")
    gstin = _clean_gstin(customer.get("gstin") or customer.get("bill_to_gstin"))
    if gstin and not _GSTIN_RE.match(gstin):
        problems.append(f"Customer GSTIN '{gstin}' is not a valid 15-character GSTIN.")

    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        problems.append("No line items were extracted.")
    else:
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            if not (item.get("material_code") or item.get("description")):
                problems.append(f"Item {index}: material/description is missing.")
            if _number(item.get("quantity")) in (None, 0.0):
                problems.append(f"Item {index}: quantity is missing or zero.")
            if _number(item.get("unit_price")) is None:
                problems.append(f"Item {index}: price is missing.")
            if not item.get("unit"):
                problems.append(f"Item {index}: unit (UOM) is missing.")

    if not _get(data, "sales_order.payment_term"):
        problems.append("Payment term is missing on the PO — confirm with the customer.")

    match_block = data.get("master_match") or {}
    if not match_block.get("matched"):
        problems.append("Customer NOT matched to ZCUSTMst master — verify before SO creation.")
    for issue in match_block.get("issues") or []:
        problems.append(str(issue))

    return problems
