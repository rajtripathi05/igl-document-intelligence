"""Acrobat-style PDF/image review viewer (Streamlit HTML component).

Renders the source document with confidence-coloured overlay boxes on top of the
detected field values, and scrolls to a focused field. Pure HTML/CSS/SVG inside a
single ``components.html`` iframe — no canvas, no heavy JavaScript. Overlay boxes
are positioned as percentages of each page so they scale with the display width.

Colours mirror :mod:`utils.confidence`: green (high, 95–100), amber (review,
75–94), red (verify, <75) — so the viewer and the extracted fields share one
heatmap palette.
"""

from __future__ import annotations

import base64
import html
import io
import logging
import re

import streamlit.components.v1 as components

from field_locator import RENDER_ZOOM
from utils.confidence import band

logger = logging.getLogger(__name__)

#: RGB per confidence band (matches the ui.py palette).
_BAND_RGB = {
    "high": (34, 197, 94),
    "review": (251, 191, 36),
    "verify": (239, 68, 68),
}


def render_pages(
    file_bytes: bytes, mime_type: str
) -> tuple[list[bytes], list[tuple[int, int]]]:
    """Rasterize the document to page PNGs at the viewer's render zoom.

    Returns:
        ``(page_png_bytes, page_sizes)`` where ``page_sizes`` are ``(width_px,
        height_px)`` at :data:`field_locator.RENDER_ZOOM` (the box coordinate space).
    """
    if mime_type == "application/pdf":
        try:
            import fitz  # PyMuPDF

            pages: list[bytes] = []
            sizes: list[tuple[int, int]] = []
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page in doc:
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM))
                    pages.append(pixmap.tobytes("png"))
                    sizes.append((pixmap.width, pixmap.height))
            return pages, sizes
        except Exception:  # noqa: BLE001
            logger.exception("PDF rasterization for viewer failed.")
            return [], []

    if mime_type.startswith("image/"):
        try:
            from PIL import Image

            with Image.open(io.BytesIO(file_bytes)) as image:
                size = (image.width, image.height)
            return [file_bytes], [size]
        except Exception:  # noqa: BLE001
            logger.exception("Image sizing for viewer failed.")
            return [file_bytes], [(1000, 1400)]

    return [], []


def _safe_id(path: str) -> str:
    """Turn a dotted path into a DOM-safe id fragment."""
    return re.sub(r"[^A-Za-z0-9_]", "_", path)


def build_viewer_html(
    pages: list[bytes],
    sizes: list[tuple[int, int]],
    boxes_by_path: dict[str, list[dict[str, float]]],
    confidence_by_path: dict[str, int],
    *,
    labels: dict[str, str] | None = None,
    focus_path: str | None = None,
) -> str:
    """Build the self-contained viewer HTML (embedded images + overlay boxes)."""
    labels = labels or {}
    # Group boxes by page for efficient rendering.
    per_page: dict[int, list[tuple[str, dict[str, float]]]] = {}
    for path, boxes in boxes_by_path.items():
        for box in boxes:
            per_page.setdefault(int(box.get("page", 0)), []).append((path, box))

    focus_id = _safe_id(focus_path) if focus_path else ""

    page_blocks: list[str] = []
    for index, png in enumerate(pages):
        width, height = sizes[index] if index < len(sizes) else (1000, 1400)
        data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        overlays: list[str] = []
        for path, box in per_page.get(index, []):
            score = int(confidence_by_path.get(path, 90))
            r, g, b = _BAND_RGB.get(band(score), _BAND_RGB["review"])
            left = box["x0"] / width * 100.0
            top = box["y0"] / height * 100.0
            w = max(box["x1"] - box["x0"], 1) / width * 100.0
            h = max(box["y1"] - box["y0"], 1) / height * 100.0
            is_focus = path == focus_path
            classes = "iglbox focus" if is_focus else "iglbox"
            dom_id = "focus-target" if is_focus else f"box_{_safe_id(path)}"
            title = html.escape(f"{labels.get(path, path)} · {score}%")
            overlays.append(
                f'<div class="{classes}" id="{dom_id}" title="{title}" '
                f'style="left:{left:.3f}%;top:{top:.3f}%;width:{w:.3f}%;height:{h:.3f}%;'
                f"--c:{r},{g},{b};\"></div>"
            )
        page_blocks.append(
            f'<div class="iglpage"><div class="iglpage-no">Page {index + 1}</div>'
            f'<div class="iglpage-inner"><img src="{data_url}" alt="page {index + 1}"/>'
            f'{"".join(overlays)}</div></div>'
        )

    body = "".join(page_blocks) or (
        '<div class="iglempty">No preview available for this file type.</div>'
    )

    return f"""
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0B1220; font-family:-apple-system,Segoe UI,Roboto,sans-serif; }}
  .iglwrap {{ padding:8px; }}
  .iglpage {{ margin:0 0 16px 0; }}
  .iglpage-no {{ color:#8aa0c6; font-size:11px; letter-spacing:.06em;
                 text-transform:uppercase; margin:0 0 4px 2px; }}
  .iglpage-inner {{ position:relative; width:100%; border-radius:10px;
                    overflow:hidden; box-shadow:0 6px 24px rgba(0,0,0,.45); }}
  .iglpage-inner img {{ display:block; width:100%; height:auto; }}
  .iglbox {{ position:absolute; border:2px solid rgba(var(--c),.95);
             background:rgba(var(--c),.16); border-radius:3px; pointer-events:none;
             box-shadow:0 0 0 1px rgba(var(--c),.35); transition:background .2s; }}
  .iglbox.focus {{ border-width:3px; background:rgba(var(--c),.30);
                   box-shadow:0 0 0 3px rgba(var(--c),.45), 0 0 22px rgba(var(--c),.65);
                   animation:iglpulse 1.4s ease-in-out infinite; }}
  @keyframes iglpulse {{ 0%,100%{{opacity:.65;}} 50%{{opacity:1;}} }}
  .iglempty {{ color:#8aa0c6; padding:40px; text-align:center; }}
</style></head>
<body><div class="iglwrap">{body}</div>
<script>
  (function() {{
    var f = document.getElementById("focus-target");
    if (f) {{ f.scrollIntoView({{behavior:"smooth", block:"center"}}); }}
  }})();
</script>
</body></html>
"""


def render_viewer(
    pages: list[bytes],
    sizes: list[tuple[int, int]],
    boxes_by_path: dict[str, list[dict[str, float]]],
    confidence_by_path: dict[str, int],
    *,
    labels: dict[str, str] | None = None,
    focus_path: str | None = None,
    height: int = 760,
) -> None:
    """Render the review viewer into the app."""
    viewer_html = build_viewer_html(
        pages,
        sizes,
        boxes_by_path,
        confidence_by_path,
        labels=labels,
        focus_path=focus_path,
    )
    components.html(viewer_html, height=height, scrolling=True)
