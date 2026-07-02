"""Shared helpers to turn document parts into inline image data URLs.

Providers that speak the OpenAI-compatible chat API (OpenRouter, and future
OpenAI/DeepSeek/Qwen backends) send images as ``data:`` URLs. Native-PDF parts
are rasterized to page PNGs here so any such provider can consume scanned or
digital PDFs uniformly. Gemini keeps its native multimodal path and does not use
this module.
"""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)

#: Cap pages rasterized from a single PDF part (keeps token cost bounded).
_MAX_PDF_PAGES = 15
#: Rasterization zoom (~150 DPI) for PDF pages sent as images.
_PDF_ZOOM = 2.0


def _data_url(data: bytes, mime_type: str) -> str:
    """Encode raw bytes as a base64 ``data:`` URL."""
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _rasterize_pdf(pdf_bytes: bytes, zoom: float, max_pages: int) -> list[bytes]:
    """Rasterize up to ``max_pages`` PDF pages to PNG bytes (best-effort)."""
    try:
        import fitz  # PyMuPDF
    except Exception:  # noqa: BLE001 - without PyMuPDF we cannot rasterize
        logger.warning("PyMuPDF unavailable; cannot rasterize PDF for this provider.")
        return []

    pages: list[bytes] = []
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for index, page in enumerate(doc):
                if index >= max_pages:
                    break
                pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                pages.append(pixmap.tobytes("png"))
    except Exception:  # noqa: BLE001 - degrade gracefully
        logger.exception("PDF rasterization failed.")
    return pages


def parts_to_image_urls(
    parts: list[tuple[bytes, str]],
    *,
    max_pdf_pages: int = _MAX_PDF_PAGES,
    pdf_zoom: float = _PDF_ZOOM,
) -> list[str]:
    """Convert document parts into a list of inline image ``data:`` URLs.

    PDF parts are rasterized to one image URL per page; image parts pass through
    directly. Every page/image of the logical document is returned in order.
    """
    urls: list[str] = []
    for data, mime in parts:
        if mime == "application/pdf":
            pages = _rasterize_pdf(data, pdf_zoom, max_pdf_pages)
            urls.extend(_data_url(png, "image/png") for png in pages)
        elif mime.startswith("image/"):
            urls.append(_data_url(data, mime))
        else:
            # Unknown binary: best-effort inline with its declared mime type.
            urls.append(_data_url(data, mime or "application/octet-stream"))
    return urls
