/* RA Posting — browser/Node port of processors/ra_posting/parser.py (v2).
 *
 * Reads SBI / IDBI bank statements (.xlsx/.xls/.xlsb/.csv via SheetJS), keeps
 * CREDIT entries only, de-duplicates overlapping pasted statement downloads,
 * derives customer names from the narrations, and produces the summary
 * workbook: Conclusion (flat) + one sheet per bank + All Banks.
 *
 * Runs entirely CLIENT-SIDE — bank data never leaves the user's machine.
 * Identity of a transaction = canonical timestamp + narration + reference +
 * amount (running balance deliberately excluded — retroactive postings shift
 * later balances between downloads and would fake uniqueness).
 *
 * Works in the browser (globals XLSX, ExcelJS) and in Node (pass libs in).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.RAParser = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const SUMMARY_COLUMNS = ["Date", "Customer Name", "Amount", "Document No.", "Mode", "Bank Name"];
  const TITLE_LINES = ["we will refer CR entries only", "summary of customers"];
  const CONCLUSION_COLUMNS = ["Customer Name", "Date", "Time", "Document No.", "Mode", "Bank Name", "Amount"];

  const MODE_WORDS = [
    [/\bRTGS\b/, "RTGS"], [/\bNEFT\b/, "NEFT"], [/\bIMPS\b/, "IMPS"], [/\bUPI\b/, "UPI"],
    [/\bCHEQUE\b/, "Cheque"], [/\bCHQ\b/, "Cheque"], [/\bCLG\b/, "Cheque"], [/\bCTS\b/, "Cheque"],
    [/\bCASH\b/, "Cash"], [/\bINB\b/, "INB"],
  ];
  const SLASH_MODES = new Set(["IMPS", "NEFT", "RTGS", "UPI"]);
  const KNOWN_BANKS = ["SBI", "IDBI", "HDFC", "ICICI", "AXIS", "PNB", "BOB", "CANARA", "UNION", "KOTAK"];
  const JUNK_SEGMENTS = /^(BATCH?|BILL|BILLS|PAY|PYMT|PAYMENT|PAYMENTS|INV|INVOICE|ONLINE|OTHERS?|TRANSFER|BANK\s*NOT?|IMPS|NEFT|RTGS|UPI)\b[-\s]*\S*$/i;

  /* ---------- small helpers ---------- */

  const S = (v) => (v === null || v === undefined) ? "" : String(v);
  const norm = (v) => S(v).toLowerCase().replace(/[^a-z0-9]/g, "");
  const round2 = (x) => Math.round((x + Number.EPSILON) * 100) / 100;

  function num(v) {
    if (v === null || v === undefined) return null;
    if (typeof v === "number") return isFinite(v) ? v : null;
    let t = S(v).trim();
    if (t === "" || t === "-" || t === "--") return null;
    const negative = t.startsWith("(") && t.endsWith(")");
    t = t.replace(/[^0-9.]/g, "");
    if (t === "" || t === ".") return null;
    const n = parseFloat(t);
    if (!isFinite(n)) return null;
    return negative ? -n : n;
  }

  const pad2 = (n) => String(n).padStart(2, "0");

  function serialToDate(serial) {
    // Excel serial (days since 1899-12-30), keeps the time fraction.
    const ms = Math.round((serial - 25569) * 86400 * 1000); // 25569 = 1970-01-01
    return new Date(ms); // interpret as UTC-naive; use UTC getters below
  }

  function fmtDate(v) {
    if (v === null || v === undefined) return "";
    if (v instanceof Date) return `${pad2(v.getUTCDate())}/${pad2(v.getUTCMonth() + 1)}/${v.getUTCFullYear()}`;
    let t = S(v).trim();
    if (!t) return "";
    const serial = Number(t);
    if (isFinite(serial) && serial >= 20000 && serial <= 80000) {
      const d = serialToDate(Math.floor(serial));
      return `${pad2(d.getUTCDate())}/${pad2(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`;
    }
    t = t.split(/\s+/)[0];
    let m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (m) return `${pad2(+m[3])}/${pad2(+m[2])}/${m[1]}`;
    m = t.match(/^(\d{1,2})[\/](\d{1,2})[\/](\d{4})$/);
    if (m) return `${pad2(+m[1])}/${pad2(+m[2])}/${m[3]}`;
    m = t.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
    if (m) return `${pad2(+m[1])}/${pad2(+m[2])}/${m[3]}`;
    m = t.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (m) return `${pad2(+m[1])}/${pad2(+m[2])}/${m[3]}`;
    m = t.match(/^(\d{1,2})-([A-Za-z]{3})-(\d{4})$/);
    if (m) {
      const months = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
      const mo = months[m[2].toLowerCase()];
      if (mo) return `${pad2(+m[1])}/${pad2(mo)}/${m[3]}`;
    }
    m = t.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{2})$/);
    if (m) return `${pad2(+m[1])}/${pad2(+m[2])}/20${m[3]}`;
    return t;
  }

  function canonDatetime(v) {
    // 'YYYY-MM-DD HH:MM:SS' canonical form for de-duplication.
    if (v === null || v === undefined) return "";
    if (v instanceof Date)
      return `${v.getUTCFullYear()}-${pad2(v.getUTCMonth() + 1)}-${pad2(v.getUTCDate())} ${pad2(v.getUTCHours())}:${pad2(v.getUTCMinutes())}:${pad2(v.getUTCSeconds())}`;
    let t = S(v).trim();
    if (!t) return "";
    const serial = Number(t);
    if (isFinite(serial) && serial >= 20000 && serial <= 80000) {
      const d = serialToDate(serial);
      return canonDatetime(d);
    }
    t = t.replace(/\.\d+$/, "");
    let m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{1,2}):(\d{2}):(\d{2})$/);
    if (m) return `${m[1]}-${pad2(+m[2])}-${pad2(+m[3])} ${pad2(+m[4])}:${m[5]}:${m[6]}`;
    m = t.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})[ T](\d{1,2}):(\d{2}):(\d{2})$/);
    if (m) return `${m[3]}-${pad2(+m[2])}-${pad2(+m[1])} ${pad2(+m[4])}:${m[5]}:${m[6]}`;
    m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (m) return `${m[1]}-${pad2(+m[2])}-${pad2(+m[3])} 00:00:00`;
    m = t.match(/^(\d{1,2})[\/](\d{1,2})[\/](\d{4})$/);
    if (m) return `${m[3]}-${pad2(+m[2])}-${pad2(+m[1])} 00:00:00`;
    m = t.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
    if (m) return `${m[3]}-${pad2(+m[2])}-${pad2(+m[1])} 00:00:00`;
    return t;
  }

  function dateSortKey(display) {
    const m = display.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    return m ? `${m[3]}${m[2]}${m[1]}` : "";
  }

  function mode(desc) {
    const t = S(desc).toUpperCase();
    if (t.includes("BY BILL") || t.includes("LCBD")) return "Bill/LC";
    for (const [re, label] of MODE_WORDS) if (re.test(t)) return label;
    const m = t.trim().match(/^([A-Z]{4})([RN])\d/);
    if (m) return m[2] === "R" ? "RTGS" : "NEFT";
    return "";
  }

  const cleanNameTail = (v) => S(v).replace(/\s+/g, " ").trim().replace(/^[\s.\-*\/]+|[\s.\-*\/]+$/g, "").trim();

  function lettersRatio(t) {
    if (!t) return 0;
    let letters = 0;
    for (const c of t) if (/[A-Za-z]/.test(c)) letters++;
    return letters / t.length;
  }

  function looksLikeName(t) {
    const c = cleanNameTail(t);
    return c.length >= 3 && lettersRatio(c.replace(/ /g, "")) >= 0.7;
  }

  const junkSegment = (t) => JUNK_SEGMENTS.test(cleanNameTail(t));

  function heuristicName(desc, ref) {
    const text = S(desc).trim();
    const reftext = S(ref).replace(/\s+/g, " ").trim();

    if (reftext) {
      let m = reftext.match(/\/\s*([A-Za-z][A-Za-z0-9 .&()\-]{2,})\s*$/);
      if (m && looksLikeName(m[1])) return cleanNameTail(m[1]);
      m = reftext.match(/TRANSFER FROM\s+\d+\s+([A-Za-z][A-Za-z .&()\-]{2,}?)\s*\//i);
      if (m && looksLikeName(m[1])) return cleanNameTail(m[1]);
    }
    if (!text) return "";
    const body = text.replace(/^\s*BY TRANSFER[-\s]*/i, "");

    let m = body.match(/--\s*([A-Za-z][A-Za-z0-9 .&()\-]{2,})\s*$/);
    if (m && looksLikeName(m[1])) return cleanNameTail(m[1]);

    if (body.includes("/")) {
      const parts = body.split("/").map((p) => p.trim());
      const head = (parts[0].toUpperCase().split(/\s+/).pop()) || "";
      if (parts.length >= 3 && SLASH_MODES.has(head)) {
        for (const part of parts.slice(2))
          if (looksLikeName(part) && !junkSegment(part)) return cleanNameTail(part);
      }
    }

    if (body.includes("*")) {
      const segments = body.split("*").map(cleanNameTail);
      let lastRef = 0;
      segments.forEach((s, i) => {
        if (s.length >= 10 && /\d/.test(s) && /^[A-Za-z0-9]+$/.test(s)) lastRef = i;
      });
      let candidates = segments.slice(lastRef + 1).filter((s) => looksLikeName(s) && !junkSegment(s));
      if (!candidates.length)
        candidates = segments.slice(1).filter((s) => looksLikeName(s) && !junkSegment(s));
      if (candidates.length) return candidates[0];
    }

    m = body.match(/^(?:NEFT|RTGS|IMPS|UPI)\s*-\s*[A-Za-z0-9]+\s*-\s*(.+)$/i);
    if (m && looksLikeName(m[1])) return cleanNameTail(m[1]);

    if (/^[A-Za-z0-9]{10,}\s/.test(body) && /\d/.test(body.split(/\s+/)[0])) {
      const rest = body.replace(/^[A-Za-z0-9]{10,}\s+/, "");
      if (looksLikeName(rest)) return cleanNameTail(rest);
    }

    m = body.match(/^([A-Za-z][A-Za-z .&()\-]{2,}?)\s+\d{6,}$/);
    if (m && looksLikeName(m[1])) return cleanNameTail(m[1]);

    m = body.match(/^BULK POSTING[-\s]*BY\s+(.+?)[-\s]*$/i);
    if (m) {
      const t2 = cleanNameTail(m[1]).toLowerCase();
      return t2.replace(/\b\w/g, (c) => c.toUpperCase());
    }

    if (/^CREDIT[-\s]*CHQ/i.test(body)) return "";

    if (body.includes("-")) {
      const tail = cleanNameTail(body.split("-").pop());
      if (looksLikeName(tail)) return tail;
    }
    const cleaned = cleanNameTail(body);
    return looksLikeName(cleaned) ? cleaned : "";
  }

  function utrFromText(text) {
    const upper = S(text).toUpperCase();
    for (const tok of upper.match(/[A-Z0-9]{10,}/g) || [])
      if (/\d/.test(tok) && /[A-Z]/.test(tok)) return tok;
    const digits = S(text).match(/\d{10,}/g);
    return digits ? digits[0] : "";
  }

  function docNo(desc, chequeNo, ref) {
    const d = S(desc);
    const cheque = S(chequeNo).trim();
    if (cheque && !["0", "0.0", "nan"].includes(cheque)) return cheque;

    let m = d.match(/UTR NO[:\s]*([A-Z0-9]{8,})/i);
    if (m) return m[1];
    m = d.match(/\bCHQ\s*\.?\s*(\d{4,})/i);
    if (m) return m[1];
    m = d.match(/(?:NEFT|RTGS|IMPS|UPI)[-\/\s]*([A-Z0-9]{6,})/i);
    if (m && m[1].toUpperCase() !== "TRANSFER") return m[1];
    const utr = utrFromText(d);
    if (utr) return utr;

    let r = S(ref).replace(/TRANSFER\s+(FROM|TO)\s+\d+/gi, " ");
    m = r.match(/([A-Z]{2,}[0-9][A-Z0-9]{4,})/);
    if (m) return m[1];
    return utrFromText(r);
  }

  /* ---------- sheet reading + block detection ---------- */

  function sheetToMatrix(XLSXlib, ws) {
    return XLSXlib.utils.sheet_to_json(ws, { header: 1, raw: true, defval: "" });
  }

  function headerSignature(cells) {
    const set = new Set(cells.filter(Boolean));
    const arr = [...set];
    if (arr.some((c) => c.startsWith("debit")) && arr.some((c) => c.startsWith("credit"))) return "SBI";
    if (set.has("crdr") && arr.some((c) => c.startsWith("amount"))) return "IDBI";
    return null;
  }

  function findBlocks(matrix) {
    const blocks = [];
    for (let i = 0; i < matrix.length; i++) {
      const cells = matrix[i].map(norm);
      const style = headerSignature(cells);
      if (!style) continue;
      const colmap = {};
      cells.forEach((c, pos) => { if (c && !(c in colmap)) colmap[c] = pos; });
      blocks.push([i, style, colmap]);
    }
    return blocks;
  }

  function col(colmap, ...predicates) {
    for (const p of predicates)
      for (const key of Object.keys(colmap))
        if (typeof p === "string" ? key === p : p(key)) return key;
    return null;
  }

  function cell(row, colmap, key) {
    if (key === null) return "";
    const pos = colmap[key];
    if (pos === undefined || pos >= row.length) return "";
    return S(row[pos]).trim();
  }

  function rawCell(row, colmap, key) {
    if (key === null) return "";
    const pos = colmap[key];
    if (pos === undefined || pos >= row.length) return "";
    return row[pos];
  }

  function parseBlock(matrix, start, end, style, colmap, bank) {
    const dateKey = col(colmap, "txndate", (k) => k.includes("txndate"), (k) => k.startsWith("date"), (k) => k.includes("valuedate"));
    const descKey = col(colmap, "description", (k) => k.includes("descr"), (k) => k.includes("narrat"), (k) => k.includes("particular"));
    let crdrKey = null, amountKey, chequeKey = null, refKey = null;
    if (style === "IDBI") {
      crdrKey = col(colmap, "crdr");
      amountKey = col(colmap, (k) => k.startsWith("amount"));
      chequeKey = col(colmap, "chequeno", (k) => k.includes("cheque"));
    } else {
      amountKey = col(colmap, "credit", (k) => k.startsWith("credit"));
      refKey = col(colmap, (k) => k.includes("refno"), (k) => k.includes("cheque"));
    }

    const txns = [];
    for (let r = start; r < end; r++) {
      const row = matrix[r] || [];
      if (row.every((x) => S(x).trim() === "")) continue;
      if (style === "IDBI" && norm(cell(row, colmap, crdrKey)) !== "cr") continue;
      const amount = num(cell(row, colmap, amountKey));
      if (amount === null || amount <= 0) continue;
      const rawDate = rawCell(row, colmap, dateKey);
      const dateDisplay = fmtDate(rawDate);
      if (!dateDisplay) continue;
      const description = cell(row, colmap, descKey);
      const cheque = cell(row, colmap, chequeKey);
      const ref = cell(row, colmap, refKey);
      txns.push({
        date: dateDisplay,
        rawDate: rawDate,
        description: description,
        ref: ref,
        amount: round2(amount),
        docNo: docNo(description, cheque, ref),
        mode: mode(description),
        bank: bank,
        nameRaw: heuristicName(description, ref),
      });
    }
    return txns;
  }

  const txnKey = (t) => [
    canonDatetime(t.rawDate) || t.date,
    t.description.replace(/\s+/g, " ").trim().toUpperCase(),
    S(t.ref).replace(/\s+/g, " ").trim().toUpperCase(),
    t.amount,
  ].join("");

  function dedupeBlocks(blocksTxns) {
    const seen = new Set();
    const unique = [];
    let total = 0;
    for (const txns of blocksTxns)
      for (const t of txns) {
        total++;
        const key = txnKey(t);
        if (seen.has(key)) continue;
        seen.add(key);
        unique.push(t);
      }
    return [unique, total - unique.length];
  }

  function bankLabel(sheetName, style, filename) {
    const upper = S(sheetName).toUpperCase().replace(/[^A-Z]/g, "");
    if (KNOWN_BANKS.includes(upper)) return upper;
    const f = S(filename).toUpperCase();
    for (const b of KNOWN_BANKS) if (new RegExp(`\\b${b}\\b`).test(f)) return b;
    return style;
  }

  /* ---------- grouping ---------- */

  function canonical(name) {
    let t = S(name).toUpperCase()
      .replace(/\bPRIVATE\b/g, "PVT").replace(/\bLIMITED\b/g, "LTD")
      .replace(/\bPVT\.\B/g, "PVT").replace(/\bLTD\.\B/g, "LTD");
    return t.replace(/[^A-Z0-9]/g, "");
  }

  function mergeTruncated(names) {
    const byKey = {};
    for (const name of names) {
      const key = canonical(name);
      if (key && (!(key in byKey) || name.length > byKey[key].length)) byKey[key] = name;
    }
    const keys = Object.keys(byKey).sort((a, b) => b.length - a.length);
    const resolve = {};
    for (const key of keys) {
      if (key.length < 8) continue;
      const longer = keys.filter((k) => k !== key && k.startsWith(key));
      if (longer.length === 1) resolve[key] = resolve[longer[0]] || longer[0];
    }
    const mapping = {};
    for (const name of names) {
      const key = canonical(name);
      const finalKey = resolve[key] || key;
      mapping[name] = byKey[finalKey] || name;
    }
    return mapping;
  }

  function displayName(t, display) {
    const raw = t.cleanName || t.nameRaw || "(Unknown)";
    return display[raw] || "(Unknown)";
  }

  function buildRows(transactions) {
    const display = mergeTruncated(transactions.map((t) => t.cleanName || t.nameRaw || "(Unknown)"));
    const groups = {};
    for (const t of transactions) {
      const name = displayName(t, display);
      (groups[name] = groups[name] || []).push(t);
    }
    const rows = [];
    let grand = 0;
    for (const name of Object.keys(groups).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))) {
      let subtotal = 0;
      const entries = groups[name].slice().sort((a, b) =>
        (dateSortKey(a.date) + a.amount).toString().localeCompare((dateSortKey(b.date) + b.amount).toString()));
      entries.sort((a, b) => dateSortKey(a.date).localeCompare(dateSortKey(b.date)) || a.amount - b.amount);
      for (const t of entries) {
        subtotal += t.amount;
        rows.push({ "Date": t.date, "Customer Name": name, "Amount": round2(t.amount),
                    "Document No.": t.docNo, "Mode": t.mode, "Bank Name": t.bank });
      }
      rows.push({ "Date": "", "Customer Name": `${name} Total`, "Amount": round2(subtotal),
                  "Document No.": "", "Mode": "", "Bank Name": "" });
      grand += subtotal;
    }
    if (Object.keys(groups).length)
      rows.push({ "Date": "", "Customer Name": "GRAND TOTAL", "Amount": round2(grand),
                  "Document No.": "", "Mode": "", "Bank Name": "" });
    return [rows, round2(grand), Object.keys(groups).length];
  }

  function txnTime(t) {
    const canon = canonDatetime(t.rawDate);
    if (canon.length >= 19) {
      const time = canon.slice(11, 19);
      return time === "00:00:00" ? "" : time;
    }
    return "";
  }

  function buildConclusionRows(transactions) {
    const display = mergeTruncated(transactions.map((t) => t.cleanName || t.nameRaw || "(Unknown)"));
    const decorated = transactions.map((t) => {
      const name = displayName(t, display);
      return [name.toLowerCase(), dateSortKey(t.date), txnTime(t), t, name];
    });
    decorated.sort((a, b) =>
      a[0].localeCompare(b[0]) || a[1].localeCompare(b[1]) || a[2].localeCompare(b[2]));
    return decorated.map(([, , time, t, name]) => ({
      "Customer Name": name, "Date": t.date, "Time": time, "Document No.": t.docNo,
      "Mode": t.mode, "Bank Name": t.bank, "Amount": round2(t.amount),
    }));
  }

  /* ---------- Excel output (ExcelJS) ---------- */

  const isTotalRow = (row) => {
    const n = S(row["Customer Name"]);
    return n === "GRAND TOTAL" || n.endsWith(" Total");
  };

  function styleHeader(cellRef) {
    cellRef.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF1F4E78" } };
    cellRef.font = { bold: true, color: { argb: "FFFFFFFF" }, size: 11 };
    cellRef.alignment = { horizontal: "center", vertical: "middle" };
    cellRef.border = borderThin();
  }
  const borderThin = () => ({
    top: { style: "thin", color: { argb: "FFBBBBBB" } }, left: { style: "thin", color: { argb: "FFBBBBBB" } },
    bottom: { style: "thin", color: { argb: "FFBBBBBB" } }, right: { style: "thin", color: { argb: "FFBBBBBB" } },
  });

  function writeSummarySheet(wb, title, rows) {
    const ws = wb.addWorksheet(title.slice(0, 31));
    ws.mergeCells(1, 1, 1, SUMMARY_COLUMNS.length);
    ws.getCell(1, 1).value = TITLE_LINES[0];
    ws.getCell(1, 1).font = { bold: true, italic: true, color: { argb: "FF7F7F00" } };
    ws.mergeCells(2, 1, 2, SUMMARY_COLUMNS.length);
    ws.getCell(2, 1).value = TITLE_LINES[1];
    ws.getCell(2, 1).font = { bold: true, size: 12 };
    SUMMARY_COLUMNS.forEach((h, i) => styleHeader(ws.getCell(3, i + 1), ws.getCell(3, i + 1).value = h));
    rows.forEach((row, r) => {
      const isTotal = isTotalRow(row);
      const isGrand = row["Customer Name"] === "GRAND TOTAL";
      SUMMARY_COLUMNS.forEach((h, c) => {
        const cl = ws.getCell(r + 4, c + 1);
        cl.value = row[h] === "" ? null : row[h];
        cl.border = borderThin();
        if (h === "Amount" && typeof row[h] === "number") {
          cl.numFmt = "#,##0.00"; cl.alignment = { horizontal: "right" };
        }
        if (isTotal) {
          cl.font = { bold: true };
          cl.fill = { type: "pattern", pattern: "solid", fgColor: { argb: isGrand ? "FFDDEBF7" : "FFF2F2F2" } };
        }
      });
    });
    const widths = { "Date": 12, "Customer Name": 38, "Amount": 16, "Document No.": 24, "Mode": 10, "Bank Name": 12 };
    SUMMARY_COLUMNS.forEach((h, i) => { ws.getColumn(i + 1).width = widths[h] || 14; });
    ws.views = [{ state: "frozen", ySplit: 3 }];
  }

  function writeConclusionSheet(wb, rows) {
    const ws = wb.addWorksheet("Conclusion");
    CONCLUSION_COLUMNS.forEach((h, i) => styleHeader(ws.getCell(1, i + 1), ws.getCell(1, i + 1).value = h));
    rows.forEach((row, r) => {
      CONCLUSION_COLUMNS.forEach((h, c) => {
        const cl = ws.getCell(r + 2, c + 1);
        cl.value = row[h] === "" ? null : row[h];
        cl.border = borderThin();
        if (h === "Amount") { cl.numFmt = "#,##0.00"; cl.alignment = { horizontal: "right" }; }
      });
    });
    const widths = { "Customer Name": 38, "Date": 12, "Time": 10, "Document No.": 24, "Mode": 10, "Bank Name": 12, "Amount": 16 };
    CONCLUSION_COLUMNS.forEach((h, i) => { ws.getColumn(i + 1).width = widths[h] || 14; });
    ws.views = [{ state: "frozen", ySplit: 1 }];
    ws.autoFilter = { from: "A1", to: `G${Math.max(rows.length + 1, 2)}` };
  }

  /* ---------- entry point ---------- */

  /**
   * run(files, libs) -> result
   *   files: [{name, data: ArrayBuffer|Uint8Array}]
   *   libs:  {XLSX, ExcelJS}  (globals used when omitted, for the browser)
   * Returns {stats, warnings, conclusionRows, perBankRows, combinedRows,
   *          workbookBuffer (Promise-resolved Uint8Array via buildWorkbook)}
   */
  function run(files, libs) {
    const XLSXlib = (libs && libs.XLSX) || (typeof XLSX !== "undefined" ? XLSX : null);
    if (!XLSXlib) throw new Error("SheetJS (XLSX) library not available");

    const warnings = [];
    const bankBlocks = {};

    for (const file of files) {
      let wb;
      try {
        wb = XLSXlib.read(file.data, { type: "array", raw: true, cellDates: false, dense: false });
      } catch (e) {
        warnings.push(`${file.name}: could not read file (${e.message}).`);
        continue;
      }
      let recognised = false;
      for (const sheetName of wb.SheetNames) {
        const matrix = sheetToMatrix(XLSXlib, wb.Sheets[sheetName]);
        const blocks = findBlocks(matrix);
        if (!blocks.length) continue;
        recognised = true;
        const boundaries = blocks.map((b) => b[0]).concat([matrix.length]);
        blocks.forEach(([headerRow, style, colmap], index) => {
          const bank = bankLabel(sheetName, style, file.name);
          const txns = parseBlock(matrix, headerRow + 1, boundaries[index + 1], style, colmap, bank);
          if (txns.length) (bankBlocks[bank] = bankBlocks[bank] || []).push(txns);
        });
      }
      if (!recognised)
        warnings.push(`${file.name}: unrecognised format — expected SBI (Debit/Credit columns) or IDBI (CR/DR + Amount columns) on at least one sheet. Skipped.`);
    }

    let transactions = [];
    let duplicatesRemoved = 0;
    for (const bank of Object.keys(bankBlocks).sort()) {
      const [unique, removed] = dedupeBlocks(bankBlocks[bank]);
      duplicatesRemoved += removed;
      transactions = transactions.concat(unique);
    }
    if (duplicatesRemoved)
      warnings.push(`Removed ${duplicatesRemoved} duplicate entries caused by overlapping statement downloads pasted into the same workbook.`);

    for (const t of transactions) t.cleanName = t.nameRaw || "(Unknown)";

    const perBankRows = {};
    const perBankTotals = {};
    for (const bank of [...new Set(transactions.map((t) => t.bank))].sort()) {
      const [rows, total] = buildRows(transactions.filter((t) => t.bank === bank));
      perBankRows[bank] = rows;
      perBankTotals[bank] = total;
    }
    const [combinedRows, grandTotal, customers] = buildRows(transactions);
    const conclusionRows = buildConclusionRows(transactions);

    const stats = {
      files: files.length,
      credit_entries: transactions.length,
      duplicates_removed: duplicatesRemoved,
      customers: customers,
      total_amount: grandTotal,
      per_bank_total: perBankTotals,
      banks: Object.keys(perBankRows),
    };

    async function buildWorkbook(ExcelJSlib) {
      const Excel = ExcelJSlib || (libs && libs.ExcelJS) || (typeof ExcelJS !== "undefined" ? ExcelJS : null);
      if (!Excel) throw new Error("ExcelJS library not available");
      const wb = new Excel.Workbook();
      if (conclusionRows.length) writeConclusionSheet(wb, conclusionRows);
      for (const bank of Object.keys(perBankRows).sort()) writeSummarySheet(wb, bank, perBankRows[bank]);
      if (Object.keys(perBankRows).length > 1) writeSummarySheet(wb, "All Banks", combinedRows);
      if (!wb.worksheets.length) writeSummarySheet(wb, "Customer Summary", []);
      return new Uint8Array(await wb.xlsx.writeBuffer());
    }

    return { stats, warnings, conclusionRows, perBankRows, combinedRows, buildWorkbook };
  }

  return { run, heuristicName, docNo, mode, fmtDate, canonDatetime,
           CONCLUSION_COLUMNS, SUMMARY_COLUMNS };
});
