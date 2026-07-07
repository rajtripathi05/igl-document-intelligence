"""Combined benchmark for IGP + Log Book — runs on the real machine (.venv).

For each improvement iteration:  run_bench.bat  →  read outputs/bench_report.txt.

Phase 0: (re)build processors/igp/templates/igp_format.xlsx from the uploaded
         'Formate' sheet of samples/IGP SAMPLES/tsmp.XLSX.
Phase IGP: extract every processors/igp/samples/*.pdf via the real pipeline
         (real Gemini), print the 14 Formate fields per document (flagging
         multi-line cells), coverage %, tokens; build the Formate register.
Phase LOG: run the Log Book engine on the sample images; print batch pairing +
         field coverage; build the register.

Usage:  python _bench.py [igp|logbook|both]   (default: both)
"""
from __future__ import annotations

import io
import sys
import time
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
OUT = BASE / "outputs"
OUT.mkdir(exist_ok=True)
REPORT = OUT / "bench_report.txt"
WHICH = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()

_buf = io.StringIO()


def log(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    _buf.write(line + "\n")
    try:
        REPORT.write_text(_buf.getvalue(), encoding="utf-8")
    except Exception:
        pass


def show(v, width=46):
    if v is None:
        return "·"
    s = str(v).replace("\n", " ⏎ ")
    return s if len(s) <= width else s[:width - 1] + "…"


log("=" * 78)
log("IGP + LOG BOOK BENCHMARK |", time.strftime("%Y-%m-%d %H:%M:%S"), "| which:", WHICH)
log("=" * 78)

import config
from processors.bootstrap import bootstrap_processors
from processors.registry import get_processor
bootstrap_processors()
log("provider:", config.settings.ai_provider, "| model:", config.settings.default_model,
    "| has_key:", config.has_ai_key())

# ── Phase 0: prepare IGP Formate template ───────────────────────────────────
try:
    import openpyxl
    src = BASE / "samples" / "IGP SAMPLES" / "tsmp.XLSX"
    dst = BASE / "processors" / "igp" / "templates" / "igp_format.xlsx"
    wb = openpyxl.load_workbook(src)
    for nm in list(wb.sheetnames):
        if nm != "Formate":
            del wb[nm]
    dst.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dst)
    log("[0] IGP template ready:", dst.name)
except Exception:
    log("[0] template prep FAILED:\n", traceback.format_exc())

# Clear the extraction cache for the processors under test so prompt/schema edits
# actually take effect on each benchmark run (cache key ignores prompt file edits
# within the same prompt_version).
try:
    cache_dir = OUT / "cache"
    cleared = 0
    keep_cache = any(a.lower() == "keep" for a in sys.argv[2:])
    if cache_dir.exists() and not keep_cache:
        pats = []
        if WHICH in ("igp", "both"):
            pats.append("igp_*.json")
        if WHICH in ("logbook", "both"):
            pats.append("logbook_*.json")
        for pat in pats:
            for f in cache_dir.glob(pat):
                f.unlink()
                cleared += 1
    log(f"[0] cleared {cleared} cache entries for fresh extraction")
except Exception:
    log("[0] cache clear failed:\n", traceback.format_exc())

IGP_FIELDS = [
    ("PO NO", "purchase_order.po_number"), ("Mat Doc No", "gate_pass.material_document_number"),
    ("Gatepass No.", "gate_pass.gate_pass_number"), ("Entry DATE", "gate_pass.entry_date"),
    ("Entry time", "gate_pass.entry_time"), ("VENDOR Code", "vendor.code"),
    ("VENDOR NAME", "vendor.name"), ("Delivery Note", "delivery.delivery_note"),
    ("DOC DATE", "delivery.document_date"), ("Vehicle No.", "delivery.vehicle_number"),
    ("Transporter Code", "transporter.code"), ("Transporter NAME", "transporter.name"),
    ("Name", "transporter.driver_name"), ("Transport GR No.", "transporter.gr_number"),
    ("NET VAL", "value.net_value_doc_currency"), ("Manual IGP", "gate_pass.manual_igp"),
    ("SUGER DESP", "quality.sugar_despatch"), ("BRIX DESP.", "quality.brix_despatch"),
    ("STRENGTH OF SDS", "quality.strength_of_sds"),
]


def gp(d, path):
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


# ── Phase IGP ───────────────────────────────────────────────────────────────
if WHICH in ("igp", "both"):
    try:
        log("\n[IGP] REAL EXTRACTION")
        from document_state import DocumentState
        from processing import assign_processor, extract_document
        from utils.file_handler import guess_mime_type
        import consolidated_excel

        igp = get_processor("igp")
        pdfs = sorted((BASE / "processors" / "igp" / "samples").glob("*.pdf"))
        only = next((a.split("=", 1)[1] for a in sys.argv[2:] if a.startswith("only=")), None)
        if only:
            pdfs = [p for p in pdfs if only.lower() in p.name.lower()]
        log("  sample PDFs:", len(pdfs), (f"(filter: {only})" if only else ""))
        docs = []
        cov = {name: 0 for name, _ in IGP_FIELDS}
        multi = {name: 0 for name, _ in IGP_FIELDS}
        tot_tokens = 0
        for pdf in pdfs:
            data = pdf.read_bytes()
            doc = DocumentState(doc_id=pdf.name, filename=pdf.name, file_bytes=data,
                                mime_type=guess_mime_type(pdf.name))
            assign_processor(doc, igp)
            t0 = time.time()
            extract_document(doc)
            dt = time.time() - t0
            usage = doc.usage or {}
            tot_tokens += usage.get("total_tokens", 0)
            log(f"\n  ── {pdf.name}  ({dt:.0f}s, conf={doc.confidence}, "
                f"status={doc.status}, tokens={usage.get('total_tokens',0)})")
            if doc.status not in ("done",) and doc.error:
                log("     ERROR:", doc.error)
            for name, path in IGP_FIELDS:
                v = gp(doc.data or {}, path)
                if v not in (None, ""):
                    cov[name] += 1
                    if isinstance(v, str) and "\n" in v:
                        multi[name] += 1
                log(f"     {name:<16}: {show(v)}")
            docs.append(doc)

        n = max(len(pdfs), 1)
        log("\n  [IGP] COVERAGE (non-null / %d docs):" % len(pdfs))
        log("   " + " | ".join(f"{name}={cov[name]}" + (f"(ML{multi[name]})" if multi[name] else "")
                                for name, _ in IGP_FIELDS))
        try:
            reg = consolidated_excel.build_register(igp, docs)
            (OUT / "igp_formate_register.xlsx").write_bytes(reg)
            log("  register saved: igp_formate_register.xlsx", f"({len(reg)} bytes)")
        except Exception:
            log("  register build FAILED:\n", traceback.format_exc())
        log(f"  IGP tokens total ~{tot_tokens}")
    except Exception:
        log("[IGP] FAILED:\n", traceback.format_exc())

# ── Phase LOG BOOK ──────────────────────────────────────────────────────────
if WHICH in ("logbook", "both"):
    try:
        log("\n[LOG BOOK] REAL EXTRACTION (all sample folders)")
        lb = get_processor("logbook")
        root = BASE / "samples" / "LOGBOOK SAMPLES"
        folders = sorted([d for d in root.iterdir() if d.is_dir()])
        onlyf = next((a.split("=", 1)[1] for a in sys.argv[2:] if a.startswith("only=")), None)
        if onlyf:
            folders = [d for d in folders if onlyf.lower() in d.name.lower()]
        keyf = ["reactor", "date", "batch_no", "product_name", "previous_reactor_line",
                "rm:LA", "rm:KOH", "rm:EO", "ps:unloading.start", "remarks"]
        all_batches = 0
        all_records = []
        for folder in folders:
            imgs = sorted(list(folder.glob("*.jpeg")) + list(folder.glob("*.jpg"))
                          + list(folder.glob("*.png")))
            if not imgs:
                continue
            payload = [(p.name, p.read_bytes()) for p in imgs]
            t0 = time.time()
            res = lb.run_logbook(payload, groups={p.name: folder.name for p in imgs})
            dt = time.time() - t0
            st = res["stats"]
            all_batches += st["batches"]
            all_records += res["records"]
            log(f"\n  ▸ {folder.name}: {len(imgs)} imgs -> main={st['main_pages']} "
                f"remarks={st['remarks_pages']} batches={st['batches']} in {dt:.0f}s "
                f"(total cols={len(res.get('columns', []))})")
            spec_cols = [c["name"] for c in res.get("column_defs", [])
                         if c.get("group") == "Complete Analysis / Specification"]
            log(f"      spec cols ({len(spec_cols)}): " + ", ".join(spec_cols))
            try:
                (OUT / ("logbook_" + folder.name.replace(" ", "_") + "_register.xlsx")).write_bytes(res["excel_bytes"])
            except Exception:
                pass
            for w in res.get("warnings", [])[:4]:
                log("      warn:", w)
            for r in res["records"]:
                log(f"      • prod={show(r.get('product_name'),16)} "
                    f"batch={show(r.get('batch_no'),16)} "
                    f"prevRL={show(r.get('previous_reactor_line'),8)} "
                    f"form={r.get('form_type')} LA={r.get('rm:LA')} KOH={r.get('rm:KOH')} "
                    f"EO={r.get('rm:EO')} RM4={show(r.get('rm:4'),8)}({show(r.get('rmname:4'),10)}) "
                    f"unl={r.get('ps:unloading.start')}-{r.get('ps:unloading.finish')} "
                    f"pages={r.get('pages')} rem={'Y' if r.get('remarks') else 'N'}")
        filled = {k: 0 for k in keyf}
        for r in all_records:
            for k in keyf:
                if r.get(k) not in (None, ""):
                    filled[k] += 1
        nb = max(all_batches, 1)
        log(f"\n  [LOG] TOTAL batches across all products: {all_batches}")
        log("  [LOG] key-field fill %: "
            + " ".join(f"{k}={round(100 * filled[k] / nb)}" for k in keyf))
    except Exception:
        log("[LOG BOOK] FAILED:\n", traceback.format_exc())

log("\n" + "=" * 78)
log("BENCHMARK COMPLETE @", time.strftime("%H:%M:%S"))
log("=" * 78)
