"""Locate extracted field values inside the source document (hybrid).

Powers the Acrobat-style review viewer: each extracted value is mapped to one or
more rectangles on a page so the viewer can draw a confidence-coloured overlay
and scroll to it.

Strategy (hybrid):
1. **Text-anchor (primary, free, reliable for digital PDFs)** — PyMuPDF
   ``page.search_for`` finds the value's text; rectangles are returned in the
   render pixel space (PDF points × zoom) so the viewer can position overlays.
2. **AI bounding-box (fallback, on-demand)** — for values text search cannot
   locate (scanned/handwritten, reformatted numbers), the AI is asked for boxes
   for a labelled list. This is a document-agnostic gateway call — it lives here,
   NOT in any processor's schema/prompt — so the plugin architecture is untouched.

Coordinates are always returned in the SAME pixel space the viewer renders at
(:data:`RENDER_ZOOM`), as ``{path: [ {page, x0, y0, x1, y1} ]}``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Rasterization zoom the review viewer renders at; box coords use the same space.
RENDER_ZOOM = 2.0
#: Cap rectangles kept per field (avoid highlighting every occurrence of a token).
_MAX_BOXES_PER_FIELD = 3
#: Minimum search-term length (single characters produce noisy matches).
_MIN_TERM_LEN = 2


def _search_terms(value: Any) -> list[str]:
    """Return candidate text tokens to search for a field value (most specific first)."""
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, float):
        terms: list[str] = []
        if value.is_integer():
            terms.append(str(int(value)))
        terms.append(f"{value:g}")
        return [t for t in dict.fromkeys(terms) if len(t) >= _MIN_TERM_LEN]
    if isinstance(value, int):
        return [str(value)] if len(str(value)) >= _MIN_TERM_LEN else []
    text = str(value).strip()
    if len(text) < _MIN_TERM_LEN:
        return []
    terms = [text]
    first_line = text.splitlines()[0].strip()
    if first_line and first_line != text and len(first_line) >= _MIN_TERM_LEN:
        terms.append(first_line)
    return terms


def locate(
    file_bytes: bytes,
    mime_type: str,
    values: dict[str, Any],
    *,
    zoom: float = RENDER_ZOOM,
    max_boxes_per_field: int = _MAX_BOXES_PER_FIELD,
) -> dict[str, list[dict[str, float]]]:
    """Locate field values in a PDF via text search (best-effort).

    Args:
        file_bytes: The original document bytes.
        mime_type: The document MIME type (only PDFs are text-searchable).
        values: ``{dotted_path: value}`` to locate.
        zoom: Render zoom; returned coordinates are in this pixel space.
        max_boxes_per_field: Cap of rectangles kept per field.

    Returns:
        ``{path: [ {page, x0, y0, x1, y1} ]}`` for values that were found.
    """
    if mime_type != "application/pdf":
        return {}
    try:
        import fitz  # PyMuPDF
    except Exception:  # noqa: BLE001
        logger.warning("PyMuPDF unavailable; cannot locate fields.")
        return {}

    located: dict[str, list[dict[str, float]]] = {}
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for path, value in values.items():
                for term in _search_terms(value):
                    boxes = _search_document(doc, term, zoom, max_boxes_per_field)
                    if boxes:
                        located[path] = boxes
                        break
    except Exception:  # noqa: BLE001 - locating must never break the review UI
        logger.exception("Field text-location failed.")
    return located


def _search_document(doc: Any, term: str, zoom: float, cap: int) -> list[dict[str, float]]:
    """Search every page for a term; return boxes from the first page that hits."""
    for page_index, page in enumerate(doc):
        try:
            rects = page.search_for(term, quads=False)
        except Exception:  # noqa: BLE001
            rects = []
        if rects:
            return [
                {
                    "page": page_index,
                    "x0": rect.x0 * zoom,
                    "y0": rect.y0 * zoom,
                    "x1": rect.x1 * zoom,
                    "y1": rect.y1 * zoom,
                }
                for rect in rects[:cap]
            ]
    return []


def locate_with_ai(
    values: dict[str, Any],
    parts: list[tuple[bytes, str]],
    page_sizes: list[tuple[int, int]],
    *,
    labels: dict[str, str] | None = None,
) -> dict[str, list[dict[str, float]]]:
    """Ask the AI for bounding boxes of values text search could not locate.

    Document-agnostic and on-demand. Uses the shared gateway (provider-agnostic).
    Returns coordinates in the same pixel space as :func:`locate` (render zoom),
    derived from the model's normalized (0–1) boxes and the known page sizes.

    Args:
        values: ``{path: value}`` still needing a location.
        parts: The rendered page images as ``(png_bytes, "image/png")`` — the same
            order/space as ``page_sizes``.
        page_sizes: ``[(width_px, height_px)]`` for each rendered page.
        labels: Optional ``{path: human_label}`` to help the model.

    Returns:
        ``{path: [ {page, x0, y0, x1, y1} ]}`` (may be empty on any failure).
    """
    if not values or not parts or not page_sizes:
        return {}

    labels = labels or {}
    catalog = [
        {"path": path, "label": labels.get(path, path), "value": str(val)}
        for path, val in values.items()
        if str(val).strip()
    ]
    if not catalog:
        return {}

    instruction = (
        "You are a document-layout locator. For each field in the list, find where "
        "its value appears on the page images and return its bounding box. Pages are "
        "1-indexed in the order provided. Respond ONLY with JSON of the form "
        '{"locations": [{"path": "<path>", "page": <1-based-int>, '
        '"box": [x0, y0, x1, y1]}]} where box coordinates are NORMALIZED fractions '
        "between 0 and 1 relative to that page's width/height (x from left, y from "
        "top). Omit any field you cannot confidently locate.\n\n"
        f"FIELDS:\n{json.dumps(catalog, ensure_ascii=False)}"
    )

    try:
        from config import ai_gateway

        response = ai_gateway.extract(
            system_prompt="",
            instruction=instruction,
            parts=parts,
            json_mode=True,
        )
        payload = json.loads(response.text)
    except Exception:  # noqa: BLE001 - fallback is best-effort
        logger.exception("AI field location failed.")
        return {}

    out: dict[str, list[dict[str, float]]] = {}
    for loc in payload.get("locations", []) or []:
        path = loc.get("path")
        box = loc.get("box")
        page = loc.get("page")
        if not path or not isinstance(box, list) or len(box) != 4:
            continue
        try:
            page_index = int(page) - 1
            width, height = page_sizes[page_index]
            coords = [float(c) for c in box]
        except (TypeError, ValueError, IndexError):
            continue
        # The model is asked for normalized fractions (0–1). If it returned some
        # already >1 (a stray pixel value), divide by the larger fraction seen so
        # everything stays within the page; then clamp to [0, 1].
        span = max(coords) or 1.0
        frac = [min(max(c / span if span > 1.5 else c, 0.0), 1.0) for c in coords]
        x0, y0, x1, y1 = frac
        out[path] = [
            {
                "page": page_index,
                "x0": min(x0, x1) * width,
                "y0": min(y0, y1) * height,
                "x1": max(x0, x1) * width,
                "y1": max(y0, y1) * height,
            }
        ]
    return out
