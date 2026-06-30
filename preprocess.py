"""OCR preprocessing applied before AI extraction.

Improves recognition on hard inputs (mobile photos, low-quality scans, rotated
or skewed pages, noisy faxes) by auto-orienting, deskewing, denoising, and
enhancing contrast/sharpness. It runs uniformly for every processor.

Policy:
- **Digital (text-layer) PDFs** pass through untouched — Gemini reads the native
  PDF and preprocessing would only lose fidelity.
- **Scanned/image-only PDFs** are rasterized per page and enhanced, then sent as
  images (one logical document across all pages).
- **Image uploads** are enhanced and sent as a single image.

OpenCV (``opencv-python-headless``) is used for deskew + denoise when available;
otherwise a Pillow-only path is used. Every step is defensive — a preprocessing
failure degrades gracefully and never blocks extraction.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: Total characters of embedded text above which a PDF is treated as "digital".
_TEXT_LAYER_THRESHOLD = 40
#: Cap on rasterized pages from a scanned PDF (keeps token cost bounded).
_MAX_SCANNED_PAGES = 15
#: Rasterization zoom for scanned PDF pages (≈150–200 DPI equivalent).
_RASTER_ZOOM = 2.0


@dataclass(frozen=True)
class DocumentPart:
    """One part of a document to send to the model.

    Attributes:
        data: Raw bytes (PDF or PNG image).
        mime_type: MIME type of ``data``.
    """

    data: bytes
    mime_type: str


def prepare(file_bytes: bytes, mime_type: str) -> list[DocumentPart]:
    """Return the document parts to send to the model after preprocessing.

    Args:
        file_bytes: Raw uploaded bytes.
        mime_type: Uploaded MIME type.

    Returns:
        One or more :class:`DocumentPart` objects. Always returns at least the
        original content so extraction can proceed even if enhancement fails.
    """
    try:
        if mime_type == "application/pdf":
            if _pdf_has_text_layer(file_bytes):
                return [DocumentPart(file_bytes, "application/pdf")]
            parts = _rasterize_and_enhance_pdf(file_bytes)
            return parts or [DocumentPart(file_bytes, "application/pdf")]
        if mime_type.startswith("image/"):
            return [DocumentPart(_enhance_image_bytes(file_bytes), "image/png")]
    except Exception:  # noqa: BLE001 - preprocessing must never break extraction
        logger.exception("Preprocessing failed; sending original document.")
    return [DocumentPart(file_bytes, mime_type)]


def _pdf_has_text_layer(file_bytes: bytes) -> bool:
    """True if the PDF carries a usable embedded text layer (i.e. not scanned)."""
    try:
        import fitz  # PyMuPDF

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            chars = sum(len(page.get_text().strip()) for page in doc)
        return chars >= _TEXT_LAYER_THRESHOLD
    except Exception:  # noqa: BLE001 - default to "scanned" on probe failure
        logger.debug("PDF text-layer probe failed; treating as scanned.", exc_info=True)
        return False


def _rasterize_and_enhance_pdf(file_bytes: bytes) -> list[DocumentPart]:
    """Rasterize each page of a scanned PDF to an enhanced PNG part."""
    import fitz  # PyMuPDF

    parts: list[DocumentPart] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for index, page in enumerate(doc):
            if index >= _MAX_SCANNED_PAGES:
                logger.info("Scanned PDF capped at %d pages.", _MAX_SCANNED_PAGES)
                break
            pixmap = page.get_pixmap(matrix=fitz.Matrix(_RASTER_ZOOM, _RASTER_ZOOM))
            enhanced = _enhance_image_bytes(pixmap.tobytes("png"))
            parts.append(DocumentPart(enhanced, "image/png"))
    logger.info("Preprocessed scanned PDF into %d enhanced page image(s).", len(parts))
    return parts


def _enhance_image_bytes(image_bytes: bytes) -> bytes:
    """Auto-orient, optionally deskew/denoise (OpenCV), and enhance an image.

    Args:
        image_bytes: Source image bytes (any Pillow-readable format).

    Returns:
        Enhanced PNG bytes (or the original bytes if enhancement fails).
    """
    try:
        from PIL import Image, ImageEnhance, ImageOps

        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)  # honour camera orientation
        if image.mode != "RGB":
            image = image.convert("RGB")

        image = _opencv_clean(image)  # deskew + denoise when OpenCV is present

        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Sharpness(image).enhance(1.4)
        image = ImageEnhance.Contrast(image).enhance(1.08)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception:  # noqa: BLE001 - return original on any failure
        logger.exception("Image enhancement failed; using original image.")
        return image_bytes


def _opencv_clean(image):
    """Deskew and denoise a PIL image with OpenCV when available; else passthrough.

    Args:
        image: A PIL RGB image.

    Returns:
        The cleaned PIL image (unchanged if OpenCV is unavailable or fails).
    """
    try:
        import cv2  # type: ignore
        import numpy as np
        from PIL import Image
    except Exception:  # noqa: BLE001 - OpenCV/NumPy optional
        return image

    try:
        array = np.array(image)
        bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)

        # Light colour denoise.
        bgr = cv2.fastNlMeansDenoisingColored(bgr, None, 5, 5, 7, 21)

        # Estimate skew from the dark text pixels and rotate to correct it.
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(threshold > 0))
        if coords.size:
            angle = cv2.minAreaRect(coords)[-1]
            angle = -(90 + angle) if angle < -45 else -angle
            if abs(angle) > 0.5:  # ignore negligible skew
                height, width = bgr.shape[:2]
                matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
                bgr = cv2.warpAffine(
                    bgr, matrix, (width, height),
                    flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
                )
                logger.debug("Deskewed image by %.2f degrees.", angle)

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)
    except Exception:  # noqa: BLE001 - any OpenCV failure → original image
        logger.debug("OpenCV cleaning failed; skipping.", exc_info=True)
        return image
