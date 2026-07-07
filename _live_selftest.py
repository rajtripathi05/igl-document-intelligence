"""Live self-test for the Log Book processor — runs on the real machine (.venv).

Validates, end to end, without the browser:
  A. imports + processor discovery (Plant Operations -> Log Book, engine=logbook)
  B. offline assembly/export (mock AI client)  -> 1 batch from main+remarks
  C. REAL AI extraction on the ECARE 243 sample images via the shared gateway,
     then assembly into batch rows + a combined register.

Writes a human-readable report to outputs/selftest_report.txt and the register to
outputs/logbook_selftest_register.xlsx. Launched by run_selftest.bat.
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
REPORT = OUT / "selftest_report.txt"

_buf = io.StringIO()


def log(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    _buf.write(line + "\n")
    try:
        REPORT.write_text(_buf.getvalue(), encoding="utf-8")
    except Exception:
        pass


log("=" * 72)
log("LOG BOOK LIVE SELF-TEST  |", time.strftime("%Y-%m-%d %H:%M:%S"))
log("=" * 72)

# ── Phase A: imports + discovery ────────────────────────────────────────────
proc = None
try:
    import config
    import departments
    from processors.bootstrap import bootstrap_processors
    from processors.registry import get_processor, all_processors

    log("\n[A] IMPORTS + DISCOVERY")
    log("  provider:", config.settings.ai_provider,
        "| default_model:", config.settings.default_model,
        "| has_key:", config.has_ai_key())
    dept = departments.get_department("plant_operations")
    log("  department 'plant_operations':", dept.name if dept else "MISSING")
    bootstrap_processors()
    log("  processors discovered:", len(all_processors()))
    proc = get_processor("logbook")
    if proc is None:
        log("  RESULT: FAIL — 'logbook' processor not registered")
    else:
        s = proc.spec
        log(f"  logbook: engine={s.engine} status={s.status} dept={s.department_key} "
            f"business_process={s.business_process!r}")
        log("  [A] PASS" if s.engine == "logbook" and s.department_key == "plant_operations"
            else "  [A] WARN — unexpected spec")
except Exception:
    log("  [A] FAIL — exception:\n", traceback.format_exc())

# ── Phase B: offline assembly/export with a mock client ─────────────────────
try:
    log("\n[B] OFFLINE ASSEMBLY/EXPORT (mock AI)")
    import importlib.util
    sp = importlib.util.spec_from_file_location(
        "logbook_engine_lt", BASE / "processors" / "logbook" / "logbook_engine.py")
    eng = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(eng)

    class _MockClient:
        def __init__(self, pages): self.pages = pages; self.i = 0
        def extract_with_confidence(self, parts):
            d = self.pages[self.i]; self.i += 1
            return d, {"batch_no": 96}

    main = {"page_type": "reactor_main", "reactor": "R-850", "date": "10/06/26",
            "batch_no": "NS2606060317", "product_name": "ECARE 243",
            "printed_product_struck": "ORCA-B",
            "raw_materials": [{"name": "LA", "actual_qty": 4998},
                              {"name": "KOH", "actual_qty": 7.5},
                              {"name": "EO", "actual_qty": 3550}],
            "process_steps": {"unloading": {"start": "18:50", "finish": "20:40"}},
            "complete_analysis": [{"parameter": "Moist", "result": "0.07"},
                                  {"parameter": "OH", "result": "168.54"}],
            "unloading_details": {"total_filled_kg": 8100},
            "join_keys": {"unloading_finish": "20:40", "total_filled_kg": 8100}}
    rem = {"page_type": "remarks", "remarks_text": "Filling completed 20:40. 09x900=8100 kg",
           "join_keys": {"unloading_finish": "20:40", "total_filled_kg": 8100}}

    class _Spec:
        use_case_key = "logbook"; department_key = "plant_operations"; prompt_version = "v1"

    res = eng.run([("m.jpg", b"x"), ("r.jpg", b"y")], client=_MockClient([main, rem]),
                  spec=_Spec(), use_cache=False, record_cost=False)
    st = res["stats"]
    r0 = res["records"][0] if res["records"] else {}
    log(f"  batches={st['batches']} (expect 1) | pages_in_row1={r0.get('pages')} (expect 2) "
        f"| product={r0.get('product_name')} | prevRL={r0.get('previous_reactor_line')} "
        f"| Meout={r0.get('spec:Meout')} (expect 0.07)")
    ok = st["batches"] == 1 and r0.get("pages") == 2 and r0.get("spec:Meout") == 0.07 \
        and r0.get("product_name") == "ECARE 243" and r0.get("previous_reactor_line") == "ORCA-B"
    log("  [B] PASS" if ok else "  [B] CHECK — see values above")
except Exception:
    log("  [B] FAIL — exception:\n", traceback.format_exc())

# ── Phase C: REAL AI extraction on ECARE 243 images ─────────────────────────
try:
    log("\n[C] REAL AI EXTRACTION — ECARE 243")
    folder = BASE / "samples" / "LOGBOOK SAMPLES" / "ECARE 243"
    imgs = sorted([p for p in folder.glob("*.jpeg")] + [p for p in folder.glob("*.jpg")])
    log("  images found:", len(imgs))
    if proc is None:
        log("  [C] SKIP — logbook processor not available")
    elif not config.has_ai_key():
        log("  [C] SKIP — no AI key configured")
    elif not imgs:
        log("  [C] SKIP — no images found at", str(folder))
    else:
        payload = [(p.name, p.read_bytes()) for p in imgs]
        groups = {p.name: "ECARE 243" for p in imgs}
        t0 = time.time()

        def _pg(done, total, name):
            log(f"    …page {min(done + 1, total)}/{total}")

        result = proc.run_logbook(payload, groups=groups, progress=_pg)
        dt = time.time() - t0
        st = result["stats"]
        log(f"  DONE in {dt:.1f}s | images={st['images']} main={st['main_pages']} "
            f"remarks={st['remarks_pages']} batches={st['batches']} products={st['products']}")
        for w in result.get("warnings", []):
            log("  warn:", w)
        log("  --- assembled batches ---")
        for r in result["records"]:
            log(f"   • prod={r.get('product_name')!r} batch={r.get('batch_no')!r} "
                f"prevRL={r.get('previous_reactor_line')!r} date={r.get('date')} "
                f"LA={r.get('rm:LA')} KOH={r.get('rm:KOH')} EO={r.get('rm:EO')} "
                f"unl={r.get('ps:unloading.start')}-{r.get('ps:unloading.finish')} "
                f"App={r.get('spec:App')} OH={r.get('spec:OH')} pages={r.get('pages')} "
                f"rem={'Y' if r.get('remarks') else 'N'}")
        reg = OUT / "logbook_selftest_register.xlsx"
        reg.write_bytes(result["excel_bytes"])
        log("  register saved:", reg.name, f"({len(result['excel_bytes'])} bytes, "
            f"{st['columns']} columns)")
        log("  [C] PASS" if st["batches"] >= 1 else "  [C] CHECK — 0 batches")
except Exception:
    log("  [C] FAIL — exception:\n", traceback.format_exc())

log("\n" + "=" * 72)
log("SELF-TEST COMPLETE — report:", str(REPORT))
log("=" * 72)
