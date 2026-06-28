"""Document preview rendering.

Renders PDF pages and images to PNG bytes for display in the UI, using PyMuPDF
for PDFs. Works for any document type — it operates purely on the uploaded
bytes and MIME type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Render scale for full-page previews and small thumbnails.
_FULL_ZOOM = 1.6
_THUMB_ZOOM = 0.35


@dataclass(frozen=True)
class RenderedDocument:
    """Rendered preview images for a document.

    Attributes:
        pages: Full-resolution PNG bytes, one per page.
        thumbnails: Thumbnail PNG bytes, one per page.
        is_image: True if the source was an image (single "page").
    """

    pages: list[bytes]
    thumbnails: list[bytes]
    is_image: bool


def render_document(document_bytes: bytes, mime_type: str) -> RenderedDocument:
    """Render a document's pages and thumbnails to PNG bytes.

    Args:
        document_bytes: Raw bytes of the uploaded document.
        mime_type: Document MIME type.

    Returns:
        A :class:`RenderedDocument`. On failure, returns empty lists so callers
        can degrade gracefully.
    """
    if mime_type == "application/pdf":
        return _render_pdf(document_bytes)
    if mime_type.startswith("image/"):
        # Images are shown directly; expose the original bytes as a single page.
        return RenderedDocument(pages=[document_bytes], thumbnails=[document_bytes], is_image=True)
    logger.debug("No preview available for MIME type %s.", mime_type)
    return RenderedDocument(pages=[], thumbnails=[], is_image=False)


def _render_pdf(document_bytes: bytes) -> RenderedDocument:
    """Rasterize each PDF page to a full image and a thumbnail."""
    try:
        import fitz  # PyMuPDF

        pages: list[bytes] = []
        thumbs: list[bytes] = []
        with fitz.open(stream=document_bytes, filetype="pdf") as doc:
            for page in doc:
                full = page.get_pixmap(matrix=fitz.Matrix(_FULL_ZOOM, _FULL_ZOOM))
                thumb = page.get_pixmap(matrix=fitz.Matrix(_THUMB_ZOOM, _THUMB_ZOOM))
                pages.append(full.tobytes("png"))
                thumbs.append(thumb.tobytes("png"))
        logger.info("Rendered %d PDF page(s) for preview.", len(pages))
        return RenderedDocument(pages=pages, thumbnails=thumbs, is_image=False)
    except Exception:  # noqa: BLE001 - preview must never break extraction
        logger.exception("PDF preview rendering failed.")
        return RenderedDocument(pages=[], thumbnails=[], is_image=False)
