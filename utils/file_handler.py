"""File handling utilities for uploaded and generated documents.

Handles reading uploaded bytes, determining MIME types, converting PDFs to
images for the model when needed, and building safe output paths.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"
IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
}

SUPPORTED_EXTENSIONS = (".pdf", *IMAGE_MIME.keys())


def guess_mime_type(filename: str) -> str:
    """Return the MIME type for a supported document filename.

    Args:
        filename: Name of the uploaded file.

    Returns:
        The corresponding MIME type string.

    Raises:
        ValueError: If the file extension is not supported.
    """
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return PDF_MIME
    if suffix in IMAGE_MIME:
        return IMAGE_MIME[suffix]
    raise ValueError(f"Unsupported file type: '{suffix}'.")


def is_pdf(filename: str) -> bool:
    """Return True if the filename has a PDF extension."""
    return Path(filename).suffix.lower() == ".pdf"


def slugify(name: str) -> str:
    """Convert a filename stem into a filesystem-safe slug.

    Args:
        name: Arbitrary input name.

    Returns:
        A lowercase slug containing only word characters and hyphens.
    """
    stem = Path(name).stem
    slug = re.sub(r"[^\w\-]+", "_", stem).strip("_")
    return slug or "purchase_order"


def build_output_path(
    outputs_dir: Path,
    original_filename: str,
    extension: str,
    suffix: str = "output",
) -> Path:
    """Build an output path inside ``outputs/`` based on the source filename.

    Args:
        outputs_dir: The outputs directory.
        original_filename: The uploaded document's filename.
        extension: Desired output extension including the leading dot.
        suffix: Naming suffix appended after the slug (e.g. ``"output"`` for
            Purchase Orders, ``"shipping_bill"`` for Shipping Bills). This lets
            each processor control its own output naming convention.

    Returns:
        A path inside ``outputs_dir``.
    """
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return outputs_dir / f"{slugify(original_filename)}_{suffix}{extension}"
