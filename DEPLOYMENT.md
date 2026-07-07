# Deploying the India Glycols Document Intelligence Platform

## ⚠️ Important: Netlify cannot host this app

This platform is a **Streamlit** application — a long‑running **Python web server**
that keeps a live WebSocket open to each user. **Netlify only hosts static files
and short serverless (JavaScript) functions; it cannot run a Streamlit/Python
server.** There is no configuration that makes `streamlit run` work on Netlify.

So we deploy the *real app* to a host that runs Python servers, and (optionally)
put a small static “indiaglycolsai” page on Netlify that links to it.

The good news: you can still get the **name `indiaglycolsai`** — either as
`indiaglycolsai.streamlit.app` (recommended, below) or a custom domain on Render.

---

## ✅ Recommended: Streamlit Community Cloud → `indiaglycolsai.streamlit.app` (free)

1. **Push this folder to a GitHub repo** (private is fine). `.env` is already in
   `.gitignore`, so **your API key is NOT uploaded** — good, keep it that way.
2. Go to **https://share.streamlit.io** → sign in with GitHub → **Create app**.
3. Pick the repo, branch `main`, main file **`app.py`**.
4. Click **Advanced settings → Custom subdomain** and enter **`indiaglycolsai`**
   → your URL becomes **https://indiaglycolsai.streamlit.app**.
5. Open **Advanced settings → Secrets** and paste (TOML form — these become the
   environment variables the app reads):
   ```toml
   AI_PROVIDER   = "openrouter"
   AI_API_KEY    = "sk-or-...your key..."
   DEFAULT_MODEL = "google/gemini-2.5-flash"
   RETRY_MODEL   = "google/gemini-2.5-pro"
   APP_ENV       = "production"
   ```
6. **Deploy.** First build installs `requirements.txt` (a few minutes). Done.

> Rotate the OpenRouter key that currently sits in the local `.env` before going
> public, and only ever store it in the host’s Secrets manager.

---

## Alternative A: Render.com (custom domain, always‑on) — uses the included files

`Dockerfile` and `render.yaml` are included.

1. Push to GitHub (as above).
2. Render → **New + → Blueprint** → select the repo. It reads `render.yaml`.
3. In the dashboard set the **`AI_API_KEY`** secret (the other vars are preset).
4. Deploy → you get `https://indiaglycolsai.onrender.com`; add a custom domain
   (e.g. `ai.indiaglycols.com`) under **Settings → Custom Domains** if you want.

Use the **Starter** plan or higher — Streamlit needs an always‑on instance
(free tiers sleep and drop the WebSocket).

## Alternative B: Hugging Face Spaces (free, quick)

Create a **Space → Streamlit**, upload these files (or link the GitHub repo), add
the same keys under **Settings → Variables and secrets**. URL:
`https://huggingface.co/spaces/<you>/indiaglycolsai`.

## Alternative C: Docker anywhere (Azure Container Apps, AWS App Runner, a VM)

```bash
docker build -t indiaglycolsai .
docker run -p 8501:8501 \
  -e AI_PROVIDER=openrouter -e AI_API_KEY=sk-or-... \
  -e DEFAULT_MODEL=google/gemini-2.5-flash -e RETRY_MODEL=google/gemini-2.5-pro \
  indiaglycolsai
```

---

## Optional: an `indiaglycolsai` landing page on Netlify

If you specifically want something on Netlify under that name, deploy the static
page in **`deploy/netlify-landing/`** (drag‑and‑drop the folder at
https://app.netlify.com/drop, then rename the site to `indiaglycolsai` →
`indiaglycolsai.netlify.app`). It’s just a front door that links to the real app
URL from one of the options above — set that link in `index.html`.

---

## Security checklist before any public deploy
- [ ] `.env` stays out of git (already git‑ignored) — set keys as host secrets only.
- [ ] Rotate the OpenRouter key that was used during development.
- [ ] Keep `APP_ENV=production` so Developer Mode is hidden by default.
- [ ] The Developer‑Mode password is `IGL@2006` unless overridden via
      `IGL_ADMIN_PASSWORD` — change it for production.
