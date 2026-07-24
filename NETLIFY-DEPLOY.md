# Deploying IGL Document Intelligence to Netlify (web edition — no Streamlit)

The `web/` folder is a self-contained web app that replaces the Streamlit UI
for the two live Marketing processes:

| Process | How it runs on Netlify |
|---|---|
| **RA Posting** (bank statements → CR summary) | 100% in the browser. SheetJS reads `.xlsx/.xls/.xlsb/.csv`, the JS port of `processors/ra_posting/parser.py` de-duplicates and groups, ExcelJS writes the workbook (Conclusion + per-bank + All Banks). **Bank data never leaves the user's machine.** |
| **Sales Order** (customer POs → SO register) | The browser sends each PDF/photo to the serverless function `/api/extract` (`web/functions/extract.mjs`), which calls OpenRouter/Gemini with the v2 prompts + schema. Master matching (ZCUSTMst), auto-fix, validation and the one-row-per-PO register are done client-side (`web/so_engine.js`). |

Verified against the Python engine: the JS RA parser reproduces the exact
reference numbers on the suman workbook (851 credits, 251 customers,
₹5,85,87,25,798.53) and the SO matcher passes the same GSTIN/PAN/NAME test
cases as `validator.py`.

## One-time setup

1. Push this repository to GitHub/GitLab/Bitbucket.
2. In Netlify: **Add new site → Import an existing project** and pick the repo.
   `netlify.toml` is detected automatically (`base=web`, functions in
   `web/functions`) — no build command, nothing Python is installed.
3. **Site settings → Environment variables** — add:
   - `AI_API_KEY` — your OpenRouter key (or Gemini key).
   - optional `AI_PROVIDER` = `openrouter` (default) or `gemini`.
   - optional `DEFAULT_MODEL` = e.g. `google/gemini-flash-latest`.
4. Deploy. Done — every push redeploys.

RA Posting works even **without** any environment variables (fully client-side).
Sales Order needs `AI_API_KEY`, otherwise the UI shows a clear error per file.

## Updating the customer master

`web/master.json` is bundled from `processors/purchase_order/master/ZCUSTMst.xls`
(15-customer sample). Either commit a regenerated `master.json`, or simply use
the **“Replace master (ZCUSTMst.xls)”** button in the UI — the uploaded file is
parsed in the browser and applied to the session (already-processed POs are
re-matched instantly).

## Local test

```bash
npm install -g netlify-cli
cd igl-document-intelligence
netlify dev        # serves web/ + functions on http://localhost:8888
```

## Notes

- The old `deploy/netlify-landing` page (a redirect to Streamlit) is no longer
  referenced by `netlify.toml`; the Streamlit app remains available for local
  use (`run_app.bat`) but is NOT part of the Netlify deployment.
- Function limits: request body ≈ 6 MB — POs are far below this. Bank
  statements never touch the function.
- Keep `web/functions/prompts.mjs` in sync when the Sales Order prompts or
  schema change (it embeds `prompts/v2/*` and `schema/schema.json`).
