/* UI glue for the IGL Document Intelligence web edition.
 * - Sales Order: PDFs/photos -> /api/extract (Netlify Function) -> SOEngine
 *   (master match + auto-fix + validation) -> one-row-per-PO register.
 * - RA Posting: bank statements parsed 100% client-side by RAParser.
 */
(function () {
  "use strict";

  /* ---------- tiny DOM helpers ---------- */
  const $ = (id) => document.getElementById(id);
  const show = (el) => el.classList.remove("hidden");
  const hide = (el) => el.classList.add("hidden");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtAmt = (n) => typeof n === "number"
    ? n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : esc(n);

  function saveBlob(bytes, filename) {
    const blob = new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  function wireDrop(dropEl, inputEl, onFiles) {
    dropEl.addEventListener("click", () => inputEl.click());
    inputEl.addEventListener("change", () => { if (inputEl.files.length) onFiles([...inputEl.files]); inputEl.value = ""; });
    ["dragover", "dragenter"].forEach((ev) => dropEl.addEventListener(ev, (e) => { e.preventDefault(); dropEl.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => dropEl.addEventListener(ev, (e) => { e.preventDefault(); dropEl.classList.remove("over"); }));
    dropEl.addEventListener("drop", (e) => { const f = [...e.dataTransfer.files]; if (f.length) onFiles(f); });
  }

  /* ---------- tabs ---------- */
  document.querySelectorAll(".tab").forEach((btn) =>
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
      document.querySelectorAll(".panel").forEach((p) =>
        p.classList.toggle("active", p.id === "tab-" + btn.dataset.tab));
    }));

  /* ================= RA POSTING ================= */
  let raResult = null;

  async function handleRAFiles(files) {
    const progress = $("ra-progress");
    show(progress);
    progress.textContent = `Reading ${files.length} file(s)…`;
    try {
      const payload = [];
      for (const f of files) payload.push({ name: f.name, data: new Uint8Array(await f.arrayBuffer()) });
      progress.textContent = "Parsing statements, removing duplicate downloads…";
      await new Promise((r) => setTimeout(r, 30)); // let the UI paint
      raResult = RAParser.run(payload, { XLSX: window.XLSX });
      renderRA();
      progress.textContent = "Done.";
      setTimeout(() => hide(progress), 1200);
    } catch (err) {
      progress.textContent = "Error: " + err.message;
    }
  }

  function renderRA() {
    const { stats, warnings, conclusionRows } = raResult;
    const wEl = $("ra-warnings");
    if (warnings.length) { show(wEl); wEl.textContent = warnings.join("\n"); } else hide(wEl);

    show($("ra-results"));
    $("ra-summary").textContent = "Customer-wise CR summary";
    $("ra-kpis").innerHTML = [
      ["Credit entries", stats.credit_entries],
      ["Duplicates removed", stats.duplicates_removed],
      ["Customers", stats.customers],
      ["Total (₹)", fmtAmt(stats.total_amount)],
      ...Object.entries(stats.per_bank_total).map(([b, v]) => [b + " (₹)", fmtAmt(v)]),
    ].map(([k, v]) => `<div class="kpi">${esc(k)}<b>${esc(String(v))}</b></div>`).join("");

    const LIMIT = 300;
    const rows = conclusionRows.slice(0, LIMIT);
    $("ra-table").innerHTML =
      "<thead><tr>" + RAParser.CONCLUSION_COLUMNS.map((c) => `<th>${esc(c)}</th>`).join("") + "</tr></thead><tbody>" +
      rows.map((r) => "<tr>" + RAParser.CONCLUSION_COLUMNS.map((c) =>
        c === "Amount" ? `<td class="num">${fmtAmt(r[c])}</td>` : `<td>${esc(r[c])}</td>`).join("") + "</tr>").join("") +
      "</tbody>";
    $("ra-more").textContent = conclusionRows.length > LIMIT
      ? `Showing first ${LIMIT} of ${conclusionRows.length} rows — the download contains everything (Conclusion + per-bank sheets + All Banks).`
      : "The download contains the Conclusion sheet plus per-bank sheets with customer totals.";
    $("ra-download").disabled = false;
  }

  $("ra-download").addEventListener("click", async () => {
    if (!raResult) return;
    $("ra-download").disabled = true;
    try {
      const bytes = await raResult.buildWorkbook(window.ExcelJS);
      saveBlob(bytes, "ra_posting_summary.xlsx");
    } finally { $("ra-download").disabled = false; }
  });

  wireDrop($("ra-drop"), $("ra-input"), handleRAFiles);

  /* ================= SALES ORDER ================= */
  let masterRecords = [];
  let soDocs = []; // {data, problems, error, filename}

  async function loadDefaultMaster() {
    const chip = $("master-status");
    try {
      const res = await fetch("master.json");
      const json = await res.json();
      masterRecords = SOEngine.prepMaster(json);
      chip.textContent = `Master: ${masterRecords.length} customers (bundled ZCUSTMst)`;
      chip.className = "chip ok";
    } catch {
      chip.textContent = "Master: not loaded — upload ZCUSTMst.xls";
      chip.className = "chip warn";
    }
  }

  function parseMasterWorkbook(arrayBuffer) {
    const wb = XLSX.read(arrayBuffer, { type: "array", raw: true });
    const norm = (v) => String(v ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
    for (const sheetName of wb.SheetNames) {
      const matrix = XLSX.utils.sheet_to_json(wb.Sheets[sheetName], { header: 1, raw: true, defval: "" });
      const hdrIdx = matrix.findIndex((row) => {
        const cells = row.map(norm);
        return cells.includes("customercode") && cells.includes("customername");
      });
      if (hdrIdx < 0) continue;
      const headers = matrix[hdrIdx].map(norm);
      const col = (...names) => { for (const n of names) { const i = headers.indexOf(n); if (i >= 0) return i; } return -1; };
      const cCode = col("customercode"), cName = col("customername"),
            cGstin = col("customergstinno", "gstin"), cAddr = col("address"),
            cCity = col("city"), cPostal = col("postalcode", "pincode"), cRegion = col("gstinregiondesc");
      const partIdx = headers.map((h, i) =>
        ["houseno","street","street2","street3","street4","street5"].includes(h) ? i : -1).filter((i) => i >= 0);
      const customers = [];
      for (let r = hdrIdx + 1; r < matrix.length; r++) {
        const row = matrix[r].map((x) => String(x ?? "").trim());
        const code = cCode >= 0 ? row[cCode] || "" : "";
        const name = cName >= 0 ? row[cName] || "" : "";
        if (!code && !name) continue;
        let address = cAddr >= 0 && row[cAddr] ? row[cAddr]
          : [...partIdx.map((i) => row[i]),
             ...(cCity >= 0 ? [row[cCity]] : []), ...(cPostal >= 0 ? [row[cPostal]] : []),
             ...(cRegion >= 0 ? [row[cRegion]] : [])].filter(Boolean).join(", ");
        customers.push({ code, name, gstin: cGstin >= 0 ? row[cGstin] || "" : "",
          address, city: cCity >= 0 ? row[cCity] || "" : "", postal: cPostal >= 0 ? row[cPostal] || "" : "" });
      }
      if (customers.length) return customers;
    }
    throw new Error("Header row (Customer Code / Customer Name) not found.");
  }

  $("master-input").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const chip = $("master-status");
    try {
      const customers = parseMasterWorkbook(await f.arrayBuffer());
      masterRecords = SOEngine.prepMaster({ customers });
      chip.textContent = `Master: ${masterRecords.length} customers (${f.name})`;
      chip.className = "chip ok";
      if (soDocs.length) { // re-match already processed docs against the new master
        soDocs.filter((d) => d.data).forEach((d) => {
          SOEngine.autoFix(d.data, masterRecords);
          d.problems = SOEngine.validateDoc(d.data);
        });
        renderSO();
      }
    } catch (err) {
      chip.textContent = "Master: could not read (" + err.message + ")";
      chip.className = "chip warn";
    }
    e.target.value = "";
  });

  function toBase64(arrayBuffer) {
    const bytes = new Uint8Array(arrayBuffer);
    let binary = "";
    const CHUNK = 0x8000;
    for (let i = 0; i < bytes.length; i += CHUNK)
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
    return btoa(binary);
  }

  const MIME = { pdf: "application/pdf", png: "image/png", jpg: "image/jpeg",
                 jpeg: "image/jpeg", webp: "image/webp" };

  async function handleSOFiles(files) {
    const progress = $("so-progress");
    show(progress);
    let done = 0;
    for (const f of files) {
      progress.textContent = `Extracting ${++done}/${files.length}: ${f.name} …`;
      const ext = f.name.split(".").pop().toLowerCase();
      const mime = MIME[ext];
      const entry = { filename: f.name, data: null, problems: [], error: null };
      if (!mime) {
        entry.error = "Unsupported file type.";
      } else {
        try {
          const res = await fetch("/api/extract", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ filename: f.name, mime, data: toBase64(await f.arrayBuffer()) }),
          });
          const payload = await res.json();
          if (!payload.ok) throw new Error(payload.error || `HTTP ${res.status}`);
          const doc = payload.data || {};
          doc.metadata = doc.metadata || {};
          doc.metadata.source = Object.assign({}, doc.metadata.source, { filename: f.name });
          SOEngine.autoFix(doc, masterRecords);
          entry.data = doc;
          entry.problems = SOEngine.validateDoc(doc);
        } catch (err) {
          entry.error = String(err.message || err);
        }
      }
      soDocs.push(entry);
      renderSO();
    }
    progress.textContent = "Done.";
    setTimeout(() => hide(progress), 1200);
  }

  const SO_PREVIEW = [
    ["Source File", (d) => d.metadata?.source?.filename],
    ["Sold/Bill to party", (d) => d.sales_order?.sold_to_party],
    ["PO No.", (d) => d.sales_order?.customer_po_number],
    ["PO date", (d) => d.sales_order?.customer_po_date],
    ["Payment term", (d) => d.sales_order?.payment_term],
    ["Material | packaging", (d) => d.sales_order?.material_with_packaging],
    ["Qty.", (d) => d.sales_order?.total_quantity],
    ["Unit", (d) => d.sales_order?.unit],
    ["Price", (d) => d.sales_order?.price_summary],
    ["Master", null], // custom badge
    ["Issues", null],
  ];

  function renderSO() {
    show($("so-results"));
    const okDocs = soDocs.filter((d) => d.data);
    $("so-summary").textContent = `${soDocs.length} file(s) processed — ${okDocs.length} extracted`;
    const head = "<thead><tr>" + SO_PREVIEW.map(([h]) => `<th>${esc(h)}</th>`).join("") + "</tr></thead>";
    const body = soDocs.map((entry) => {
      if (entry.error)
        return `<tr><td>${esc(entry.filename)}</td><td colspan="${SO_PREVIEW.length - 1}">` +
               `<span class="badge err">error</span> ${esc(entry.error)}</td></tr>`;
      const d = entry.data;
      const mm = d.master_match || {};
      const cells = SO_PREVIEW.map(([h, fn]) => {
        if (h === "Master")
          return `<td>${mm.matched
            ? `<span class="badge ok">${esc(mm.method)} · ${esc(mm.customer_code)}</span>`
            : '<span class="badge no">not in master</span>'}</td>`;
        if (h === "Issues")
          return `<td title="${esc(entry.problems.join("\n"))}">${entry.problems.length}</td>`;
        const v = fn(d);
        return h === "Qty." ? `<td class="num">${esc(v ?? "")}</td>` : `<td>${esc(v ?? "")}</td>`;
      });
      return "<tr>" + cells.join("") + "</tr>";
    }).join("");
    $("so-table").innerHTML = head + "<tbody>" + body + "</tbody>";
    $("so-download").disabled = okDocs.length === 0;
  }

  $("so-download").addEventListener("click", async () => {
    const okDocs = soDocs.filter((d) => d.data).map((d) => d.data);
    if (!okDocs.length) return;
    $("so-download").disabled = true;
    try {
      const bytes = await SOEngine.buildRegister(okDocs, window.ExcelJS);
      saveBlob(bytes, "sales_order_register.xlsx");
    } finally { $("so-download").disabled = false; }
  });

  wireDrop($("so-drop"), $("so-input"), handleSOFiles);
  loadDefaultMaster();
})();
