# India Glycols — Document Intelligence Platform (Streamlit).
# A container that runs the app on ANY container host (Render, Railway, Azure
# Container Apps, AWS App Runner, a VM, etc.). NOT for Netlify — Netlify does not
# run long-lived Python servers (see DEPLOYMENT.md).
FROM python:3.11-slim

# System libs for OpenCV/PyMuPDF/Pillow image handling.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Secrets are injected by the host as environment variables at runtime:
#   AI_PROVIDER, AI_API_KEY, DEFAULT_MODEL, RETRY_MODEL  (never baked into image)
EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8501/_stcore/health'); " || exit 1

# $PORT is provided by most hosts; default to 8501 locally.
CMD streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true
