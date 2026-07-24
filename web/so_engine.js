/* Sales Order engine — browser/Node port of processors/purchase_order/validator.py.
 *
 * Given the AI-extracted JSON of a customer PO (from /api/extract), this module:
 *   1. auto-fixes dates/numbers and fills the flat SO-Step fields,
 *   2. matches the customer against the ZCUSTMst master
 *      (GSTIN exact -> PAN same-company-different-state -> fuzzy name,
 *       address PIN/city as tie-breaker) and FILLS Sold-to from the master,
 *   3. validates for SO creation,
 *   4. builds the consolidated register — ONE ROW PER UPLOADED PO — with the
 *      SO-Step columns in business order (ExcelJS).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.SOEngine = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const GSTIN_RE = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$/i;
  const PIN_RE = /\b(\d{6})\b/;
  const NAME_NOISE = new Set(["PRIVATE","PVT","LIMITED","LTD","LLP","COMPANY","CO","INDIA",
    "INDUSTRIES","INDUSTRIAL","ENTERPRISES","CORPORATION","CORP","THE"]);

  const EXPORT_COLUMNS = [
    ["Sold/Bill to party", "sales_order.sold_to_party"],
    ["Ship to party", "sales_order.ship_to_party"],
    ["Customer reference/PO No.", "sales_order.customer_po_number"],
    ["Cust. Ref./PO date", "sales_order.customer_po_date"],
    ["Payment term", "sales_order.payment_term"],
    ["Incoterm", "sales_order.incoterm"],
    ["Incoterm location", "sales_order.incoterm_location"],
    ["Material code with packaging type", "sales_order.material_with_packaging"],
    ["Plant", "sales_order.plant"],
    ["Qty.", "sales_order.total_quantity"],
    ["Unit", "sales_order.unit"],
    ["Industry key", "sales_order.industry_key"],
    ["Test report required", "sales_order.test_report_required"],
    ["Insurance", "sales_order.insurance"],
    ["Basis of delivery", "sales_order.basis_of_delivery"],
    ["Incoterm 2 location", "sales_order.incoterm2_location"],
    ["Price", "sales_order.price_summary"],
    ["Discount/credit note", "sales_order.discount_credit_note"],
    ["Schedule/dispatch date", "sales_order.schedule_dispatch_date"],
    ["ETA date", "sales_order.eta_date"],
    ["Customer Code (master)", "master_match.customer_code"],
    ["Master Match", "master_match.method"],
    ["Customer GSTIN (PO)", "customer.gstin"],
    ["Master GSTIN", "master_match.gstin"],
    ["Grand Total", "summary.grand_total"],
    ["Source File", "metadata.source.filename"],
  ];

  /* ---------- helpers ---------- */

  const S = (v) => (v === null || v === undefined) ? "" : String(v);

  function get(data, path) {
    let node = data;
    for (const part of path.split(".")) {
      if (node === null || typeof node !== "object") return null;
      node = node[part];
      if (node === undefined) return null;
    }
    return node;
  }
  function set(data, path, value) {
    const parts = path.split(".");
    let node = data;
    for (const p of parts.slice(0, -1)) {
      if (typeof node[p] !== "object" || node[p] === null) node[p] = {};
      node = node[p];
    }
    node[parts[parts.length - 1]] = value;
  }

  const note = (field, oldV, newV, reason, confidence) =>
    ({ field, old: oldV, new: newV, reason, confidence });

  function isoDate(v) {
    if (v === null || v === undefined) return null;
    const t = S(v).trim().replace(/\s+/g, " ");
    if (!t) return null;
    const pad = (n) => String(n).padStart(2, "0");
    let m = t.match(/^(\d{4})[-\/](\d{1,2})[-\/](\d{1,2})$/);
    if (m) return `${m[1]}-${pad(+m[2])}-${pad(+m[3])}`;
    m = t.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})$/);
    if (m) return `${m[3]}-${pad(+m[2])}-${pad(+m[1])}`;
    m = t.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2})$/);
    if (m) return `20${m[3]}-${pad(+m[2])}-${pad(+m[1])}`;
    const months = { jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12 };
    m = t.match(/^(\d{1,2})[\s-]([A-Za-z]{3,9})[\s,-]+(\d{4})$/);
    if (m) {
      const mo = months[m[2].slice(0, 3).toLowerCase()];
      if (mo) return `${m[3]}-${pad(mo)}-${pad(+m[1])}`;
    }
    return null;
  }

  function number(v) {
    if (v === null || v === undefined || typeof v === "boolean") return null;
    if (typeof v === "number") return isFinite(v) ? v : null;
    const t = S(v).replace(/[^0-9.\-]/g, "");
    if (t === "" || t === "-" || t === ".") return null;
    const n = parseFloat(t);
    return isFinite(n) ? n : null;
  }

  const cleanGstin = (v) => S(v).toUpperCase().replace(/[^0-9A-Z]/g, "");

  function normName(v) {
    const words = S(v).toUpperCase().replace(/[^A-Z0-9 ]/g, " ").split(/\s+/)
      .filter((w) => w && !NAME_NOISE.has(w));
    return words.join(" ");
  }

  // Ratcliff/Obershelp ratio (difflib.SequenceMatcher.ratio equivalent).
  function ratio(a, b) {
    if (!a.length && !b.length) return 1;
    const matches = matchLen(a, 0, a.length, b, 0, b.length);
    return (2 * matches) / (a.length + b.length);
  }
  function longestMatch(a, alo, ahi, b, blo, bhi) {
    let besti = alo, bestj = blo, bestsize = 0;
    const j2len = new Map();
    for (let i = alo; i < ahi; i++) {
      const newj2len = new Map();
      for (let j = blo; j < bhi; j++) {
        if (a[i] === b[j]) {
          const k = (j2len.get(j - 1) || 0) + 1;
          newj2len.set(j, k);
          if (k > bestsize) { besti = i - k + 1; bestj = j - k + 1; bestsize = k; }
        }
      }
      j2len.clear();
      for (const [k2, v2] of newj2len) j2len.set(k2, v2);
    }
    return [besti, bestj, bestsize];
  }
  function matchLen(a, alo, ahi, b, blo, bhi) {
    const [i, j, k] = longestMatch(a, alo, ahi, b, blo, bhi);
    if (!k) return 0;
    return k + matchLen(a, alo, i, b, blo, j) + matchLen(a, i + k, ahi, b, j + k, bhi);
  }

  function nameSimilarity(a, b) {
    if (!a || !b) return 0;
    if (a === b) return 1;
    const ca = a.replace(/ /g, ""), cb = b.replace(/ /g, "");
    if (ca.length >= 8 && (cb.startsWith(ca) || ca.startsWith(cb))) return 0.95;
    return ratio(a, b);
  }

  /* ---------- master matching ---------- */

  function prepMaster(masterJson) {
    const records = (masterJson.customers || masterJson || []).map((r) => ({
      code: S(r.code), name: S(r.name), normName: normName(r.name),
      gstin: cleanGstin(r.gstin), address: S(r.address),
      city: S(r.city).toUpperCase(), postal: S(r.postal),
    }));
    return records;
  }

  function matchCustomer(name, gstin, address, records) {
    const issues = [];
    const g = cleanGstin(gstin);
    const norm = normName(name);
    const pinM = S(address).match(PIN_RE);
    const pin = pinM ? pinM[1] : "";
    const addrUpper = S(address).toUpperCase();

    if (g && GSTIN_RE.test(g)) {
      for (const rec of records)
        if (rec.gstin && rec.gstin === g) {
          if (nameSimilarity(norm, rec.normName) < 0.5)
            issues.push(`GSTIN ${g} matches master customer ${rec.code} '${rec.name}' but the PO shows '${name}' — verify.`);
          return [rec, "GSTIN", issues];
        }
      const pan = g.slice(2, 12);
      const panHits = records.filter((r) => r.gstin && r.gstin.slice(2, 12) === pan);
      if (panHits.length === 1) {
        const rec = panHits[0];
        issues.push(`PO GSTIN ${g} is a different STATE registration of master customer ${rec.code} '${rec.name}' (master GSTIN ${rec.gstin}) — confirm the correct sold-to code for this state.`);
        return [rec, "PAN", issues];
      }
    }

    if (norm) {
      const scored = records
        .map((rec) => [nameSimilarity(norm, rec.normName), rec])
        .filter(([s]) => s >= 0.86)
        .sort((a, b) => b[0] - a[0]);
      if (scored.length) {
        const topScore = scored[0][0];
        let top = scored.filter(([s]) => s >= topScore - 0.02).map(([, r]) => r);
        let method = "NAME";
        if (top.length > 1) {
          const narrowed = top.filter((r) => (pin && r.postal === pin) || (r.city && addrUpper.includes(r.city)));
          if (narrowed.length === 1) { top = narrowed; method = "NAME+ADDRESS"; }
          else issues.push(`Multiple master customers share this name — picked ${top[0].code} '${top[0].name}'; verify the sold-to code.`);
        }
        const rec = top[0];
        if (g && rec.gstin && rec.gstin !== g)
          issues.push(`Name matches master customer ${rec.code} '${rec.name}' but GSTIN differs (PO: ${g}, master: ${rec.gstin}) — verify.`);
        if (pin && rec.postal && rec.postal !== pin)
          issues.push(`PIN code differs (PO address: ${pin}, master: ${rec.postal}) — possible different site of the same customer.`);
        return [rec, method, issues];
      }
    }
    return [null, "", issues];
  }

  /* ---------- auto-fix + validation (mirror of validator.py) ---------- */

  const DATE_FIELDS = [
    ["sales_order.customer_po_date", "Cust. Ref./PO date"],
    ["sales_order.schedule_dispatch_date", "Schedule/dispatch date"],
    ["sales_order.eta_date", "ETA date"],
  ];
  const ITEM_NUMBER_KEYS = ["quantity","unit_price","taxable_amount","gst_percent","gst_amount","total_amount"];

  function autoFix(data, masterRecords) {
    const notes = [];

    for (const [path, label] of DATE_FIELDS) {
      const old = get(data, path);
      const fixed = isoDate(old);
      if (fixed && fixed !== old) {
        set(data, path, fixed);
        notes.push(note(label, old, fixed, "Date normalized to ISO format", 97));
      }
    }

    const items = Array.isArray(data.items) ? data.items : [];
    items.forEach((item, idx) => {
      if (item === null || typeof item !== "object") return;
      for (const key of ITEM_NUMBER_KEYS) {
        const old = item[key];
        if (old === null || old === undefined || old === "") continue;
        const fixed = number(old);
        if (fixed !== null && fixed !== old) {
          item[key] = fixed;
          notes.push(note(`Item ${idx + 1} · ${key}`, old, fixed, "Number cleaned", 96));
        }
      }
      const dOld = item.delivery_date;
      const dFix = isoDate(dOld);
      if (dFix && dFix !== dOld) {
        item.delivery_date = dFix;
        notes.push(note(`Item ${idx + 1} · delivery_date`, dOld, dFix, "Date normalized to ISO format", 97));
      }
    });

    const customer = data.customer || {};
    const name = customer.name || customer.bill_to_name || "";
    const gstin = customer.gstin || customer.bill_to_gstin || "";
    const address = customer.address || customer.bill_to_address || "";

    const matchBlock = { matched: false, method: "", customer_code: "",
                         customer_name: "", gstin: "", address: "", issues: [] };
    if (masterRecords && masterRecords.length) {
      const [rec, method, issues] = matchCustomer(name, gstin, address, masterRecords);
      matchBlock.issues.push(...issues);
      if (rec) {
        Object.assign(matchBlock, { matched: true, method, customer_code: rec.code,
          customer_name: rec.name, gstin: rec.gstin, address: rec.address });
        const confidence = { GSTIN: 98, PAN: 90, NAME: 88, "NAME+ADDRESS": 90 }[method] || 80;
        const soldTo = `${rec.name} [${rec.code}]`;
        const oldSold = get(data, "sales_order.sold_to_party") || name;
        set(data, "sales_order.sold_to_party", soldTo);
        if (oldSold !== soldTo)
          notes.push(note("Sold/Bill to party", oldSold, soldTo,
            `Filled from customer master ZCUSTMst (matched by ${method})`, confidence));
      } else {
        matchBlock.issues.push("Customer not found in ZCUSTMst master — verify the customer or update the master file.");
      }
    } else {
      matchBlock.issues.push("Customer master file not found (ZCUSTMst).");
    }
    if (!get(data, "sales_order.sold_to_party")) set(data, "sales_order.sold_to_party", name || "");
    data.master_match = matchBlock;

    const ship = data.ship_to || {};
    if (!get(data, "sales_order.ship_to_party")) {
      const shipText = [S(ship.name).trim(), S(ship.address).trim()].filter(Boolean).join(", ");
      set(data, "sales_order.ship_to_party", shipText);
    }

    const perItem = [], quantities = [], units = [], prices = [];
    for (const item of items) {
      if (item === null || typeof item !== "object") continue;
      const material = S(item.material_code).trim();
      const description = S(item.description).trim();
      const packaging = S(item.packaging_type).trim();
      const parts = [material];
      if (description && description.toUpperCase() !== material.toUpperCase()) parts.push(description);
      if (packaging) parts.push(packaging);
      const text = parts.filter(Boolean).join(" | ");
      item.material_with_packaging = text;
      if (text && !perItem.includes(text)) perItem.push(text);
      const q = number(item.quantity);
      if (q !== null) quantities.push(q);
      const unit = S(item.unit).trim();
      if (unit && !units.includes(unit)) units.push(unit);
      const price = number(item.unit_price);
      if (price !== null) {
        const per = S(item.price_per || unit).trim();
        const pt = `${price}${per ? "/" + per : ""}`;
        if (!prices.includes(pt)) prices.push(pt);
      }
    }
    set(data, "sales_order.material_with_packaging", perItem.join("; "));
    set(data, "sales_order.unit", units.join(", "));
    set(data, "sales_order.total_quantity",
      quantities.length && units.length <= 1
        ? Math.round(quantities.reduce((a, b) => a + b, 0) * 1000) / 1000 : null);
    set(data, "sales_order.price_summary", prices.join("; "));

    const flag = get(data, "sales_order.test_report_required");
    if (flag !== null && flag !== undefined && flag !== "") {
      const t = S(flag).trim().toUpperCase();
      const normalized = ["YES","Y","TRUE","REQUIRED","1"].includes(t) ? "Yes"
        : ["NO","N","FALSE","NOT REQUIRED","0"].includes(t) ? "No" : S(flag);
      if (normalized !== flag) {
        set(data, "sales_order.test_report_required", normalized);
        notes.push(note("Test report required", flag, normalized, "Normalized to Yes/No", 95));
      }
    }

    data.validation = data.validation || {};
    data.validation.line_item_count = items.length;
    return { data, notes };
  }

  function validateDoc(data) {
    const problems = [];
    if (!get(data, "sales_order.customer_po_number")) problems.push("Customer PO number is missing.");
    const poDate = get(data, "sales_order.customer_po_date");
    if (!poDate) problems.push("Customer PO date is missing.");
    else if (isoDate(poDate) === null) problems.push("Customer PO date is not a recognizable date.");

    const customer = data.customer || {};
    if (!(customer.name || customer.bill_to_name)) problems.push("Customer (Sold-to party) name is missing.");
    const g = cleanGstin(customer.gstin || customer.bill_to_gstin);
    if (g && !GSTIN_RE.test(g)) problems.push(`Customer GSTIN '${g}' is not a valid 15-character GSTIN.`);

    const items = Array.isArray(data.items) ? data.items : [];
    if (!items.length) problems.push("No line items were extracted.");
    items.forEach((item, i) => {
      if (item === null || typeof item !== "object") return;
      if (!(item.material_code || item.description)) problems.push(`Item ${i + 1}: material/description is missing.`);
      const q = number(item.quantity);
      if (q === null || q === 0) problems.push(`Item ${i + 1}: quantity is missing or zero.`);
      if (number(item.unit_price) === null) problems.push(`Item ${i + 1}: price is missing.`);
      if (!item.unit) problems.push(`Item ${i + 1}: unit (UOM) is missing.`);
    });

    if (!get(data, "sales_order.payment_term"))
      problems.push("Payment term is missing on the PO — confirm with the customer.");

    const mm = data.master_match || {};
    if (!mm.matched) problems.push("Customer NOT matched to ZCUSTMst master — verify before SO creation.");
    for (const issue of mm.issues || []) problems.push(S(issue));
    return problems;
  }

  /* ---------- register (one row per PO) ---------- */

  async function buildRegister(docs, ExcelJSlib) {
    const Excel = ExcelJSlib || (typeof ExcelJS !== "undefined" ? ExcelJS : null);
    if (!Excel) throw new Error("ExcelJS library not available");
    const wb = new Excel.Workbook();
    const ws = wb.addWorksheet("Sales Orders");
    EXPORT_COLUMNS.forEach(([header], i) => {
      const cl = ws.getCell(1, i + 1);
      cl.value = header;
      cl.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF1F4E78" } };
      cl.font = { bold: true, color: { argb: "FFFFFFFF" }, size: 11 };
      cl.alignment = { horizontal: "center", vertical: "middle" };
    });
    docs.forEach((doc, r) => {
      EXPORT_COLUMNS.forEach(([, path], c) => {
        let v = get(doc, path);
        if (Array.isArray(v)) v = v.filter((x) => x !== null && x !== "").join("\n");
        if (typeof v === "boolean") v = v ? "Yes" : "No";
        ws.getCell(r + 2, c + 1).value = (v === "" ? null : v);
      });
    });
    EXPORT_COLUMNS.forEach(([header], i) => {
      ws.getColumn(i + 1).width = Math.min(Math.max(header.length + 4, 14), 42);
    });
    ws.views = [{ state: "frozen", ySplit: 1 }];
    ws.autoFilter = { from: "A1", to: `Z${Math.max(docs.length + 1, 2)}` };
    return new Uint8Array(await wb.xlsx.writeBuffer());
  }

  return { prepMaster, matchCustomer, autoFix, validateDoc, buildRegister,
           EXPORT_COLUMNS, isoDate, nameSimilarity, normName };
});
