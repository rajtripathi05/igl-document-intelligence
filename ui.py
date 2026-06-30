"""Presentation helpers: India Glycols branding, theming, and header.

Design language: ~70% SAP Fiori, ~30% Apple Human Interface — a clean, spacious,
premium enterprise look. All visual/branding concerns live here so ``app.py`` and
``engine.py`` stay focused on orchestration and the generic engine.

The logo is auto-detected from the ``assets/`` directory, so a logo file can be
dropped in without code changes.
"""

from __future__ import annotations

import base64
import random
import time
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Brand palette  (premium enterprise — deep navy canvas, soft elevated cards)
# ---------------------------------------------------------------------------
BG = "#0B1220"            # app canvas
CARD = "#121A2B"          # primary card
CARD_2 = "#172235"        # secondary / nested card
CARD_HOVER = "#1B2942"    # card hover lift
LINE = "#22304A"          # hairline separators (no harsh borders)

PRIMARY = "#1565C0"       # primary blue
PRIMARY_LIGHT = "#3B82F6"
PRIMARY_DARK = "#0F4C95"
ACCENT = "#22C55E"        # accent green
WARNING = "#FBBF24"       # amber
ERROR = "#EF4444"         # red

TEXT = "#FFFFFF"          # 100%
TEXT_90 = "rgba(255,255,255,0.90)"
TEXT_70 = "rgba(255,255,255,0.70)"
TEXT_40 = "rgba(255,255,255,0.40)"

COMPANY_NAME = "India Glycols Limited"
PLATFORM_NAME = "Enterprise Document Intelligence Platform"
TAGLINE = "AI-Powered · SAP-Ready Processing"

# Subtle, enterprise-friendly confidence colours (green / amber / red).
CONFIDENCE_COLORS = {
    "high": ACCENT,      # green   95-100%  Excellent
    "review": WARNING,   # amber   75-94%   Needs Review
    "verify": ERROR,     # red     0-74%    Manual Verification
}
CONFIDENCE_DOT = {"high": "🟢", "review": "🟡", "verify": "🔴"}
CONFIDENCE_MEANING = {
    "high": "Excellent",
    "review": "Needs Review",
    "verify": "Manual Verification",
}

# ---------------------------------------------------------------------------
# Department visual identity (subtle, enterprise) — colour + icon per dept.
# ---------------------------------------------------------------------------
# Each department carries a restrained accent colour and an icon used to tint
# processor cards, headers, and KPIs. Colours stay subtle: they appear only as
# soft tints, hairlines, and glows — never as large saturated fills.
DEPARTMENT_IDENTITY: dict[str, dict[str, str]] = {
    "store":        {"color": "#3B82F6", "icon": "📦"},   # Blue
    "marketing":    {"color": "#8B5CF6", "icon": "📈"},   # Purple
    "export":       {"color": "#22C55E", "icon": "🌍"},   # Green
    "finance":      {"color": "#F59E0B", "icon": "₹"},    # Gold
    "hr":           {"color": "#06B6D4", "icon": "👥"},   # Cyan
    "operations":   {"color": "#64748B", "icon": "⚙️"},   # Slate
    "supply_chain": {"color": "#14B8A6", "icon": "🚚"},   # Teal
    "chemical":     {"color": "#10B981", "icon": "🧪"},   # Emerald
    "production":   {"color": "#F97316", "icon": "🏭"},   # Orange
    # Departments without an explicitly specified identity get a sensible accent.
    "mechanical":   {"color": "#94A3B8", "icon": "🔧"},   # Steel
    "management":   {"color": "#0EA5E9", "icon": "📊"},   # Sky
}
_DEFAULT_IDENTITY = {"color": PRIMARY_LIGHT, "icon": "🏢"}


def department_identity(department_key: str) -> dict[str, str]:
    """Return the ``{"color", "icon"}`` visual identity for a department key."""
    return DEPARTMENT_IDENTITY.get(department_key, _DEFAULT_IDENTITY)


def department_color(department_key: str) -> str:
    """Return just the subtle accent colour for a department key."""
    return department_identity(department_key)["color"]

# ---------------------------------------------------------------------------
# Scientific visual identity — faint hexagonal molecular lattice (decorative)
# ---------------------------------------------------------------------------
# A tileable benzene-style hexagon grid, encoded once at import as a data URI
# and painted behind everything at very low opacity, so it evokes chemistry /
# science without ever reducing readability.
_HEX_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="56" height="98" '
    'viewBox="0 0 28 49"><g fill="none" fill-rule="evenodd">'
    '<g fill="#3FA9F5" fill-opacity="0.9">'
    '<path d="M13.99 9.25l13 7.5v15l-13 7.5L1 31.75v-15l12.99-7.5zM3 17.9v12.7l10.99 '
    '6.34 11-6.35V17.9l-11-6.34L3 17.9zM0 15l12.98-7.5V0h-2v6.35L0 12.69v2.3zm0 '
    '18.5L12.98 41v8h-2v-6.85L0 35.81v-2.3zM15 0v7.5L27.99 15H28v-2.31h-.01L17 '
    '6.35V0h-2zm0 49v-8l12.99-7.5H28v2.31h-.01L17 42.15V49h-2z"/></g></g></svg>'
)
_HEX_DATA = base64.b64encode(_HEX_SVG.encode("utf-8")).decode("ascii")


def _svg_data_uri(svg: str) -> str:
    """Encode a raw SVG string as a base64 ``data:`` URI for CSS backgrounds."""
    return "data:image/svg+xml;base64," + base64.b64encode(
        svg.encode("utf-8")
    ).decode("ascii")


# Lightweight decorative scientific glyphs used as slow-floating SVG elements.
# Each is a tiny, stroke-only shape (no fills, no script) kept near-invisible by
# very low opacity in CSS — they evoke molecules without ever drawing the eye.
_FLOAT_HEXAGON = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="90" height="90" viewBox="0 0 90 90">'
    '<polygon points="45,6 79,26 79,64 45,84 11,64 11,26" fill="none" '
    'stroke="#3B82F6" stroke-width="2"/>'
    '<circle cx="45" cy="45" r="4" fill="#3B82F6"/></svg>'
)
_FLOAT_BOND = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60" viewBox="0 0 120 60">'
    '<line x1="18" y1="30" x2="102" y2="30" stroke="#22C55E" stroke-width="2"/>'
    '<circle cx="14" cy="30" r="8" fill="none" stroke="#22C55E" stroke-width="2"/>'
    '<circle cx="106" cy="30" r="8" fill="none" stroke="#22C55E" stroke-width="2"/></svg>'
)
_FLOAT_NODE = _svg_data_uri(
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
    '<circle cx="50" cy="20" r="5" fill="#2BB0C9"/>'
    '<circle cx="20" cy="72" r="5" fill="#2BB0C9"/>'
    '<circle cx="80" cy="72" r="5" fill="#2BB0C9"/>'
    '<path d="M50 20 L20 72 M50 20 L80 72 M20 72 L80 72" fill="none" '
    'stroke="#2BB0C9" stroke-width="1.5"/></svg>'
)

_LOGO_GLOBS = ("logo.png", "logo.jpg", "logo.jpeg", "logo.svg", "logo.webp")


def find_logo(assets_dir: Path) -> Path | None:
    """Return the first matching logo file in ``assets_dir``, if any.

    Args:
        assets_dir: The assets directory to search.

    Returns:
        Path to a logo file, or None if none is present.
    """
    for name in _LOGO_GLOBS:
        candidate = assets_dir / name
        if candidate.exists():
            return candidate
    return None


def _logo_html(logo_path: Path, css_class: str = "igl-logo") -> str:
    """Build an inline-image HTML snippet for the given logo file."""
    data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    suffix = logo_path.suffix.lower().lstrip(".")
    mime = "svg+xml" if suffix == "svg" else suffix
    return (
        f'<img src="data:image/{mime};base64,{data}" '
        f'alt="{COMPANY_NAME}" class="{css_class}" />'
    )


# ---------------------------------------------------------------------------
# Global theme
# ---------------------------------------------------------------------------
def inject_theme() -> None:
    """Inject the global premium enterprise CSS (SAP Fiori × Apple HIG)."""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)
    # Decorative scientific lattice behind all content (pointer-events:none).
    # The molecular hex grid + particle cloud + company-identity motifs are all
    # painted by this layer at very low opacity; the floating SVG glyphs are a
    # second, equally faint layer of slow-drifting hexagons, bonds and nodes.
    st.markdown(
        '<div class="igl-identity" aria-hidden="true"></div>'
        '<div class="igl-molecular"></div>'
        '<div class="igl-float" aria-hidden="true">'
        '<span class="f1"></span><span class="f2"></span><span class="f3"></span>'
        '<span class="f4"></span><span class="f5"></span><span class="f6"></span>'
        "</div>",
        unsafe_allow_html=True,
    )


_THEME_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {{
    --bg: {BG};
    --card: {CARD};
    --card-2: {CARD_2};
    --card-hover: {CARD_HOVER};
    --line: {LINE};
    --primary: {PRIMARY};
    --primary-light: {PRIMARY_LIGHT};
    --primary-dark: {PRIMARY_DARK};
    --accent: {ACCENT};
    --warning: {WARNING};
    --error: {ERROR};
    --text: {TEXT};
    --text-70: {TEXT_70};
    --text-40: {TEXT_40};
    --radius: 18px;
    --radius-sm: 12px;
    --shadow: 0 8px 30px rgba(0,0,0,0.35);
    --shadow-sm: 0 4px 16px rgba(0,0,0,0.25);
    --shadow-lift: 0 16px 44px rgba(0,0,0,0.45);
}}

/* ---- Canvas & base typography -------------------------------------- */
.stApp {{
    background:
        radial-gradient(1200px 600px at 80% -10%, rgba(21,101,192,0.10), transparent 60%),
        radial-gradient(900px 500px at -10% 10%, rgba(34,197,94,0.05), transparent 55%),
        {BG};
    color: {TEXT_90};
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    -webkit-font-smoothing: antialiased;
}}
.block-container {{
    padding-top: 2.2rem;
    padding-bottom: 4rem;
    max-width: 1320px;
    position: relative; z-index: 1;
    animation: igl-fade-in 0.45s ease both;
}}
h1, h2, h3, h4, h5 {{
    font-family: 'Inter', sans-serif !important;
    color: {TEXT} !important;
    letter-spacing: -0.01em;
}}
h1 {{ font-weight: 800 !important; }}
h2, h3 {{ font-weight: 700 !important; }}
h4 {{ font-weight: 600 !important; letter-spacing: .005em; }}
p, label, .stMarkdown {{ color: {TEXT_90}; }}
hr {{ border-color: {LINE}; opacity: .6; }}

/* ---- Animations ----------------------------------------------------- */
@keyframes igl-fade-in {{ from {{ opacity:0; transform: translateY(8px); }} to {{ opacity:1; transform:none; }} }}
@keyframes igl-rise {{ from {{ opacity:0; transform: translateY(14px); }} to {{ opacity:1; transform:none; }} }}
@keyframes igl-pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:.45; }} }}
@keyframes igl-check {{ 0% {{ transform: scale(0) rotate(-12deg); opacity:0; }} 60% {{ transform: scale(1.18) rotate(0); }} 100% {{ transform: scale(1); opacity:1; }} }}
@keyframes igl-stripe {{ from {{ background-position: 0 0; }} to {{ background-position: 36px 0; }} }}
@keyframes igl-logo-in {{ 0% {{ opacity:0; transform: scale(.6) rotate(-8deg); }} 60% {{ transform: scale(1.06) rotate(0); }} 100% {{ opacity:1; transform: scale(1); }} }}
@keyframes igl-spin {{ to {{ transform: rotate(360deg); }} }}
@keyframes igl-core-pulse {{ 0%,100% {{ box-shadow:0 0 26px rgba(59,130,246,0.45), inset 0 0 16px rgba(255,255,255,0.12); }} 50% {{ box-shadow:0 0 44px rgba(59,130,246,0.75), inset 0 0 22px rgba(255,255,255,0.20); }} }}
@keyframes igl-lattice-drift {{ from {{ background-position: 0 0; }} to {{ background-position: 600px 1050px; }} }}
@keyframes igl-particles {{ from {{ transform: translate(0,0); }} to {{ transform: translate(16px,-24px); }} }}
@keyframes igl-confetti-fall {{ 0% {{ opacity:0; transform: translateY(-12px) rotate(0); }} 15% {{ opacity:1; }} 100% {{ opacity:0; transform: translateY(150px) rotate(420deg); }} }}
@keyframes igl-ring-in {{ from {{ transform: scale(.82); opacity:0; }} to {{ transform: scale(1); opacity:1; }} }}

/* ---- Header --------------------------------------------------------- */
.igl-header {{
    display: flex; align-items: center; gap: 22px;
    padding: 26px 30px; border-radius: var(--radius);
    background:
        linear-gradient(135deg, {PRIMARY_DARK} 0%, {PRIMARY} 55%, #1E6FD0 100%);
    box-shadow: var(--shadow);
    margin-bottom: 18px;
    position: relative; overflow: hidden;
    animation: igl-rise 0.5s ease both;
}}
.igl-header::after {{
    content:""; position:absolute; inset:0;
    background: radial-gradient(600px 200px at 90% -40%, rgba(255,255,255,0.16), transparent 70%);
    pointer-events:none;
}}
.igl-logo {{
    height: 60px; width: 60px; object-fit: contain;
    border-radius: 14px; background:#fff; padding: 8px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.30);
    flex-shrink: 0;
    animation: igl-logo-in .85s cubic-bezier(.2,.8,.2,1) both;
}}
.igl-head-text {{ z-index:1; }}
.igl-wordmark {{ font-size: 28px; font-weight: 800; color:#fff; line-height: 1.12; letter-spacing:-.02em; }}
.igl-accent {{ color:#BFE3FF; }}
.igl-sub {{ font-size: 14.5px; color: rgba(255,255,255,0.86); margin-top: 4px; font-weight:500; }}
.igl-head-badges {{ display:flex; gap:10px; margin-top:12px; flex-wrap:wrap; }}
.igl-tag {{
    display:inline-flex; align-items:center; gap:7px;
    padding: 5px 13px; border-radius: 999px;
    background: rgba(255,255,255,0.14); color:#fff; font-size:12px; font-weight:600;
    backdrop-filter: blur(4px);
}}
.igl-tag .dot {{ width:7px; height:7px; border-radius:999px; background:{ACCENT};
    box-shadow:0 0 0 3px rgba(34,197,94,0.25); animation: igl-pulse 2.4s ease-in-out infinite; }}

/* ---- Breadcrumb ----------------------------------------------------- */
.igl-crumb {{
    color: {TEXT_70}; font-size: 13px; font-weight:500;
    margin: 6px 2px 18px; display:flex; align-items:center; gap:8px;
}}
.igl-crumb .sep {{ color: {TEXT_40}; }}

/* ---- Generic card --------------------------------------------------- */
.igl-card {{
    background: {CARD};
    border: 1px solid {LINE};
    border-radius: var(--radius);
    padding: 22px 24px;
    margin-bottom: 16px;
    box-shadow: var(--shadow-sm);
    transition: transform .22s cubic-bezier(.2,.7,.2,1), box-shadow .22s ease, border-color .22s ease;
    animation: igl-rise 0.45s ease both;
}}
.igl-card:hover {{
    transform: translateY(-4px);
    box-shadow: var(--shadow-lift);
    border-color: rgba(59,130,246,0.35);
}}
.igl-card-title {{
    font-size: 11.5px; color: {TEXT_70}; font-weight: 700;
    text-transform: uppercase; letter-spacing: .10em; margin-bottom: 10px;
}}
.igl-metric {{ font-size: 26px; font-weight: 800; color: {TEXT}; line-height:1.1; }}
.igl-metric-label {{ font-size: 12px; color: {TEXT_70}; }}

/* ---- Document classification card ----------------------------------- */
.igl-doc-head {{
    display:flex; align-items:center; gap:14px; flex-wrap:wrap;
    background: {CARD};
    border: 1px solid {LINE};
    border-radius: var(--radius);
    padding: 18px 22px; margin: 4px 0 18px;
    box-shadow: var(--shadow-sm);
    animation: igl-rise .45s ease both;
}}
.igl-doc-icon {{
    width:44px; height:44px; border-radius: 12px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center; font-size:22px;
    background: linear-gradient(135deg, rgba(21,101,192,0.25), rgba(59,130,246,0.12));
    border:1px solid rgba(59,130,246,0.25);
}}
.igl-doc-type {{ font-size: 19px; font-weight: 700; color:{TEXT}; }}
.igl-doc-tab {{ font-weight: 600; }}
.igl-doc-meta {{ font-size:12.5px; color:{TEXT_70}; }}

/* ---- Confidence chip & meter --------------------------------------- */
.igl-conf-chip {{
    display:inline-flex; align-items:center; gap:5px;
    padding: 3px 11px; border-radius: 999px;
    font-size: 11.5px; font-weight: 700; color:#06210F;
    transition: background .35s ease;
}}
.igl-conf-meter {{
    height: 7px; border-radius: 999px; background: rgba(255,255,255,0.08);
    overflow:hidden; margin-top:7px;
}}
.igl-conf-fill {{
    height:100%; border-radius:999px;
    transition: width .6s cubic-bezier(.2,.7,.2,1), background .35s ease;
}}

/* ---- Field labels --------------------------------------------------- */
.igl-field-label {{
    display:flex; align-items:center; gap:9px; flex-wrap:wrap;
    font-size: 12.5px; color: {TEXT_70}; font-weight:600;
    margin: 2px 0 -4px;
}}

/* ---- Legend --------------------------------------------------------- */
.igl-legend {{
    display:flex; gap:18px; flex-wrap:wrap; align-items:center;
    font-size:12.5px; color:{TEXT_70};
    background: {CARD_2}; border:1px solid {LINE};
    padding:10px 16px; border-radius: var(--radius-sm); margin-bottom:14px;
}}
.igl-legend b {{ color:{TEXT}; font-weight:600; }}

/* ---- AI Gateway dashboard card -------------------------------------- */
.igl-gw {{
    background: linear-gradient(180deg, {CARD_2}, {CARD});
    border:1px solid {LINE}; border-radius: var(--radius);
    padding: 18px 20px; box-shadow: var(--shadow-sm);
    animation: igl-rise .45s ease both;
}}
.igl-gw-top {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }}
.igl-gw-title {{ font-size:12.5px; font-weight:700; letter-spacing:.06em;
    text-transform:uppercase; color:{TEXT_70}; }}
.igl-status-pill {{
    display:inline-flex; align-items:center; gap:7px;
    padding:4px 11px; border-radius:999px; font-size:12px; font-weight:700;
}}
.igl-status-pill .dot {{ width:8px; height:8px; border-radius:999px; animation: igl-pulse 2s ease-in-out infinite; }}
.igl-gw-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px 14px; }}
.igl-gw-cell .k {{ font-size:11px; color:{TEXT_40}; text-transform:uppercase; letter-spacing:.05em; }}
.igl-gw-cell .v {{ font-size:14.5px; color:{TEXT}; font-weight:600; margin-top:1px; }}

/* ---- Upload area ---------------------------------------------------- */
[data-testid="stFileUploaderDropzone"] {{
    background: {CARD} !important;
    border: 2px dashed rgba(59,130,246,0.30) !important;
    border-radius: var(--radius) !important;
    padding: 38px 24px !important;
    transition: border-color .25s ease, background .25s ease, box-shadow .25s ease, transform .25s ease;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
    border-color: {PRIMARY_LIGHT} !important;
    background: {CARD_HOVER} !important;
    box-shadow: 0 0 0 4px rgba(59,130,246,0.12), var(--shadow-sm);
    transform: translateY(-2px);
}}
[data-testid="stFileUploaderDropzone"] section,
[data-testid="stFileUploaderDropzone"] > div {{ color:{TEXT_90} !important; }}
.igl-upload-hint {{
    text-align:center; margin: -6px 0 14px;
}}
.igl-upload-hint .glyph {{ font-size:40px; line-height:1; }}
.igl-upload-hint .ttl {{ font-size:18px; font-weight:700; color:{TEXT}; margin-top:8px; }}
.igl-upload-hint .types {{
    display:flex; gap:8px; flex-wrap:wrap; justify-content:center; margin-top:12px;
}}
.igl-upload-hint .types span {{
    font-size:11.5px; font-weight:600; color:{TEXT_70};
    background:{CARD_2}; border:1px solid {LINE};
    padding:4px 11px; border-radius:999px;
}}

/* ---- Buttons (Apple-inspired) -------------------------------------- */
.stButton>button, .stDownloadButton>button {{
    border-radius: 12px !important;
    font-weight: 600 !important;
    border: 1px solid {LINE} !important;
    background: {CARD_2} !important;
    color: {TEXT} !important;
    padding: 9px 18px !important;
    transition: transform .15s ease, box-shadow .2s ease, background .2s ease, border-color .2s ease !important;
    box-shadow: var(--shadow-sm);
}}
.stButton>button:hover, .stDownloadButton>button:hover {{
    transform: translateY(-2px);
    border-color: rgba(59,130,246,0.45) !important;
    background: {CARD_HOVER} !important;
    box-shadow: var(--shadow-sm);
}}
.stButton>button:active, .stDownloadButton>button:active {{ transform: scale(0.98) translateY(0); }}
.stButton>button[kind="primary"] {{
    background: linear-gradient(135deg, {PRIMARY}, {PRIMARY_LIGHT}) !important;
    border: none !important; color:#fff !important;
    box-shadow: 0 8px 22px rgba(21,101,192,0.40) !important;
}}
.stButton>button[kind="primary"]:hover {{
    box-shadow: 0 12px 28px rgba(21,101,192,0.55) !important;
    transform: translateY(-2px);
}}

/* ---- Inputs --------------------------------------------------------- */
.stTextInput>div>div>input, .stNumberInput input, .stTextArea textarea,
.stSelectbox>div>div {{
    background: {CARD_2} !important;
    border: 1px solid {LINE} !important;
    border-radius: 10px !important;
    color: {TEXT} !important;
}}
.stTextInput>div>div>input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
    border-color: {PRIMARY_LIGHT} !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}}

/* ---- Tabs (document switcher) -------------------------------------- */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px; border-bottom: 1px solid {LINE}; padding-bottom: 2px;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent; border-radius: 10px 10px 0 0;
    padding: 9px 16px; font-weight: 600; color: {TEXT_70};
    transition: color .2s ease, background .2s ease;
}}
.stTabs [data-baseweb="tab"]:hover {{ background: {CARD_2}; color:{TEXT}; }}
.stTabs [aria-selected="true"] {{ color: {TEXT} !important; background: {CARD} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: {PRIMARY_LIGHT} !important; height:3px; border-radius:3px; }}

/* ---- Tables / data editor ------------------------------------------ */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
    border-radius: var(--radius-sm); overflow:hidden;
    border:1px solid {LINE}; box-shadow: var(--shadow-sm);
}}
[data-testid="stDataFrame"] thead tr th, [data-testid="stDataEditor"] thead tr th {{
    background: {CARD_2} !important; color:{TEXT} !important;
    font-weight:600 !important; position: sticky; top:0;
}}
[data-testid="stDataFrame"] tbody tr:hover, [data-testid="stDataEditor"] tbody tr:hover {{
    background: {CARD_HOVER} !important;
}}

/* ---- Progress bar --------------------------------------------------- */
.stProgress > div > div > div > div {{
    background: linear-gradient(90deg, {PRIMARY}, {PRIMARY_LIGHT}) !important;
}}
.stProgress > div > div > div {{ background: rgba(255,255,255,0.07) !important; border-radius:999px; }}

/* ---- Expander (accordion) ------------------------------------------ */
[data-testid="stExpander"] {{
    border:1px solid {LINE} !important; border-radius: var(--radius-sm) !important;
    background:{CARD} !important; box-shadow: var(--shadow-sm); overflow:hidden;
}}
[data-testid="stExpander"] summary {{ font-weight:600; }}
[data-testid="stExpander"] summary:hover {{ color:{PRIMARY_LIGHT}; }}

/* ---- Alerts (rounded, soft) ---------------------------------------- */
[data-testid="stAlert"] {{ border-radius: var(--radius-sm) !important; border:1px solid {LINE}; }}

/* ---- Metrics -------------------------------------------------------- */
[data-testid="stMetric"] {{
    background: {CARD}; border:1px solid {LINE}; border-radius: var(--radius-sm);
    padding: 14px 16px; box-shadow: var(--shadow-sm);
}}

/* ---- Sidebar -------------------------------------------------------- */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0A101C 0%, {BG} 100%);
    border-right: 1px solid {LINE};
    position: relative; z-index: 1;
}}
section[data-testid="stSidebar"] .block-container {{ padding-top: 1.4rem; }}
.igl-side-brand {{ display:flex; align-items:center; gap:11px; margin-bottom:4px; }}
.igl-side-logo {{ height:34px; width:34px; object-fit:contain; border-radius:9px; background:#fff; padding:4px; }}
.igl-side-name {{ font-size:15px; font-weight:700; color:{TEXT}; line-height:1.1; }}
.igl-side-sub {{ font-size:11px; color:{TEXT_40}; }}

/* ---- Processing queue ---------------------------------------------- */
.igl-queue-row {{
    display:flex; align-items:center; gap:14px;
    background:{CARD}; border:1px solid {LINE}; border-radius: var(--radius-sm);
    padding:13px 16px; margin-bottom:10px; box-shadow: var(--shadow-sm);
    animation: igl-rise .4s ease both;
}}
.igl-queue-ico {{ font-size:20px; }}
.igl-queue-name {{ font-weight:600; color:{TEXT}; font-size:14px; }}
.igl-queue-meta {{ font-size:12px; color:{TEXT_70}; }}
.igl-check {{
    display:inline-flex; align-items:center; justify-content:center;
    width:24px; height:24px; border-radius:999px; background:{ACCENT}; color:#06210F;
    font-weight:900; font-size:14px; animation: igl-check .5s cubic-bezier(.2,.9,.3,1.4) both;
}}

/* ---- Section heading ------------------------------------------------ */
.igl-section {{
    display:flex; align-items:center; gap:10px;
    font-size:18px; font-weight:700; color:{TEXT}; margin:22px 0 12px;
}}
.igl-section .bar {{ width:4px; height:20px; border-radius:3px;
    background: linear-gradient(180deg, {PRIMARY_LIGHT}, {PRIMARY}); }}

/* ---- Overall document confidence badge ----------------------------- */
.igl-overall {{
    display:flex; align-items:center; gap:16px;
    background: {CARD}; border:1px solid {LINE}; border-radius: var(--radius);
    padding:16px 20px; margin:4px 0 16px; box-shadow: var(--shadow-sm);
    animation: igl-rise .45s ease both;
}}
.igl-overall-ring {{
    width:64px; height:64px; border-radius:999px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center;
    font-size:18px; font-weight:800; color:#fff;
}}
.igl-overall-main {{ flex:1; }}
.igl-overall-label {{ font-size:11.5px; text-transform:uppercase; letter-spacing:.10em;
    color:{TEXT_70}; font-weight:700; }}
.igl-overall-value {{ font-size:20px; font-weight:800; color:{TEXT}; line-height:1.15; }}
.igl-overall-counts {{ display:flex; gap:14px; font-size:12px; color:{TEXT_70}; margin-top:4px; }}

/* ---- KPI cards (glass) --------------------------------------------- */
.igl-kpis {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr)); gap:12px; margin:6px 0 14px; }}
.igl-kpi {{
    background: linear-gradient(160deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
    border:1px solid rgba(255,255,255,0.10); border-radius: var(--radius-sm);
    padding:14px 16px; box-shadow: var(--shadow-sm), inset 0 1px 0 rgba(255,255,255,0.05);
    backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
    animation: igl-rise .4s ease both; transition: transform .2s ease, box-shadow .2s ease; }}
.igl-kpi:hover {{ transform: translateY(-3px); box-shadow: var(--shadow-lift), inset 0 1px 0 rgba(255,255,255,0.08); }}
.igl-kpi .k {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:{TEXT_40}; }}
.igl-kpi .v {{ font-size:22px; font-weight:800; color:{TEXT}; margin-top:3px;
    animation: igl-count-in .7s cubic-bezier(.2,.8,.2,1) both; }}
.igl-kpi .s {{ font-size:11.5px; color:{TEXT_70}; }}

/* ---- Lifecycle status chips ---------------------------------------- */
.igl-life {{ display:inline-flex; align-items:center; gap:6px; padding:2px 10px;
    border-radius:999px; font-size:11px; font-weight:700; }}
.igl-life.production {{ background:rgba(34,197,94,0.15); color:{ACCENT}; }}
.igl-life.testing {{ background:rgba(251,191,36,0.15); color:{WARNING}; }}
.igl-life.draft {{ background:rgba(148,163,184,0.15); color:#94A3B8; }}
.igl-life.coming_soon {{ background:rgba(59,130,246,0.13); color:{PRIMARY_LIGHT}; }}

/* ---- Coming-soon hero ---------------------------------------------- */
.igl-soon {{
    text-align:center; background: linear-gradient(180deg, {CARD_2}, {CARD});
    border:1px solid {LINE}; border-radius: var(--radius); padding:46px 28px;
    box-shadow: var(--shadow-sm); animation: igl-rise .45s ease both;
}}
.igl-soon .glyph {{ font-size:48px; }}
.igl-soon .ttl {{ font-size:22px; font-weight:800; color:{TEXT}; margin-top:12px; }}
.igl-soon .sub {{ font-size:14px; color:{TEXT_70}; margin-top:8px; max-width:520px;
    margin-left:auto; margin-right:auto; }}

/* ---- Auto-fix note rows -------------------------------------------- */
.igl-fix {{ display:flex; align-items:center; gap:10px; font-size:13px;
    padding:8px 12px; border-radius:10px; background:rgba(34,197,94,0.07);
    border:1px solid rgba(34,197,94,0.18); margin-bottom:8px; }}
.igl-fix .arrow {{ color:{TEXT_40}; }}
.igl-fix .old {{ color:{TEXT_70}; text-decoration:line-through; }}
.igl-fix .new {{ color:{ACCENT}; font-weight:700; }}

/* ---- Scientific molecular background (decorative, ~invisible) ------- */
.igl-molecular {{
    position: fixed; inset: 0; z-index: -1; pointer-events: none;
    background-image: url("data:image/svg+xml;base64,{_HEX_DATA}");
    background-size: 60px 105px; opacity: 0.05;
    animation: igl-lattice-drift 120s linear infinite;
}}
.igl-molecular::after {{
    content:""; position:absolute; inset:-20%;
    background:
        radial-gradient(2px 2px at 18% 32%, rgba(59,130,246,0.8), transparent),
        radial-gradient(2px 2px at 72% 58%, rgba(34,197,94,0.7), transparent),
        radial-gradient(1.6px 1.6px at 42% 80%, rgba(43,176,201,0.7), transparent),
        radial-gradient(1.6px 1.6px at 85% 22%, rgba(124,58,237,0.6), transparent),
        radial-gradient(2px 2px at 55% 12%, rgba(59,130,246,0.7), transparent),
        radial-gradient(1.4px 1.4px at 30% 60%, rgba(34,197,94,0.6), transparent);
    opacity: 0.6; animation: igl-particles 30s ease-in-out infinite alternate;
}}

/* ---- Company visual identity (decorative, near-invisible) ----------- */
/* India Glycols' four worlds, painted as the faintest gradient washes:
   bio-based chemicals (emerald), industrial gases (blue particle haze),
   potable spirits (flowing amber liquid) and biopharma (violet). Purely
   decorative; opacity is tiny so usability is never affected. */
.igl-identity {{
    position: fixed; inset: 0; z-index: -1; pointer-events: none; opacity: 0.5;
    background:
        radial-gradient(900px 520px at 12% 8%, rgba(16,185,129,0.06), transparent 60%),
        radial-gradient(820px 480px at 88% 18%, rgba(59,130,246,0.05), transparent 62%),
        radial-gradient(1000px 620px at 80% 96%, rgba(245,158,11,0.045), transparent 60%),
        radial-gradient(760px 500px at 6% 92%, rgba(139,92,246,0.045), transparent 62%);
    animation: igl-identity-drift 48s ease-in-out infinite alternate;
}}

/* ---- Floating scientific elements (slow, opacity < 10%) ------------- */
.igl-float {{ position: fixed; inset: 0; z-index: -1; pointer-events: none; }}
.igl-float span {{
    position: absolute; display: block; background-repeat: no-repeat;
    background-size: contain; opacity: 0.07; will-change: transform;
}}
.igl-float .f1 {{ top:14%; left:8%;  width:90px;  height:90px;
    background-image: url("{_FLOAT_HEXAGON}"); animation: igl-drift-a 26s ease-in-out infinite alternate; }}
.igl-float .f2 {{ top:62%; left:18%; width:120px; height:60px;
    background-image: url("{_FLOAT_BOND}");    animation: igl-drift-b 32s ease-in-out infinite alternate; }}
.igl-float .f3 {{ top:30%; left:82%; width:100px; height:100px;
    background-image: url("{_FLOAT_NODE}");    animation: igl-drift-c 38s ease-in-out infinite alternate; }}
.igl-float .f4 {{ top:78%; left:72%; width:70px;  height:70px;
    background-image: url("{_FLOAT_HEXAGON}"); animation: igl-drift-b 30s ease-in-out infinite alternate; }}
.igl-float .f5 {{ top:8%;  left:54%; width:90px;  height:45px;
    background-image: url("{_FLOAT_BOND}");    animation: igl-drift-c 34s ease-in-out infinite alternate; }}
.igl-float .f6 {{ top:48%; left:44%; width:80px;  height:80px;
    background-image: url("{_FLOAT_NODE}");    animation: igl-drift-a 40s ease-in-out infinite alternate; }}

/* ---- Glass enterprise card ----------------------------------------- */
.igl-glass {{
    position: relative; border-radius: var(--radius); padding: 18px 20px;
    background: linear-gradient(160deg, rgba(255,255,255,0.07), rgba(255,255,255,0.02));
    border: 1px solid rgba(255,255,255,0.10);
    backdrop-filter: blur(10px) saturate(120%);
    -webkit-backdrop-filter: blur(10px) saturate(120%);
    box-shadow: var(--shadow-sm), inset 0 1px 0 rgba(255,255,255,0.06);
    transition: transform .22s cubic-bezier(.2,.7,.2,1), box-shadow .22s ease, border-color .22s ease;
    animation: igl-rise .45s ease both;
}}
.igl-glass:hover {{
    transform: translateY(-3px);
    border-color: rgba(255,255,255,0.18);
    box-shadow: var(--shadow-lift), inset 0 1px 0 rgba(255,255,255,0.10);
}}

/* ---- Glass KPI grid (animated reveal + confidence rings) ----------- */
.igl-gkpis {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(190px,1fr)); gap:14px; margin:8px 0 16px; }}
.igl-gkpi {{ display:flex; align-items:center; gap:14px; }}
.igl-gkpi .body {{ flex:1; min-width:0; }}
.igl-gkpi .k {{ font-size:11px; text-transform:uppercase; letter-spacing:.07em; color:{TEXT_40}; }}
.igl-gkpi .v {{ font-size:24px; font-weight:800; color:{TEXT}; margin-top:2px; line-height:1.1;
    animation: igl-count-in .7s cubic-bezier(.2,.8,.2,1) both; }}
.igl-gkpi .s {{ font-size:11.5px; color:{TEXT_70}; margin-top:1px; }}
.igl-gkpi .glyph {{ width:42px; height:42px; border-radius:12px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center; font-size:20px;
    background: linear-gradient(135deg, rgba(255,255,255,0.10), rgba(255,255,255,0.02));
    border:1px solid rgba(255,255,255,0.10); }}

/* ---- Processor cards (premium, selectable) ------------------------- */
.igl-pcards {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); gap:14px; margin:6px 0 6px; }}
.igl-pcard {{
    --dept: {PRIMARY_LIGHT};
    position: relative; border-radius: var(--radius); padding: 18px 18px 16px;
    background: linear-gradient(165deg, rgba(255,255,255,0.06), rgba(255,255,255,0.015));
    border: 1px solid rgba(255,255,255,0.10);
    box-shadow: var(--shadow-sm);
    backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
    transition: transform .24s cubic-bezier(.2,.7,.2,1), box-shadow .24s ease, border-color .24s ease;
    animation: igl-rise .45s ease both; overflow: hidden;
}}
.igl-pcard::before {{
    content:""; position:absolute; left:0; top:0; bottom:0; width:4px;
    background: var(--dept); opacity:.85;
}}
.igl-pcard::after {{
    content:""; position:absolute; inset:0; border-radius:inherit; pointer-events:none;
    background: radial-gradient(360px 140px at 90% -30%, color-mix(in srgb, var(--dept) 22%, transparent), transparent 70%);
    opacity:0; transition: opacity .25s ease;
}}
.igl-pcard:hover {{
    transform: translateY(-5px);
    border-color: color-mix(in srgb, var(--dept) 55%, transparent);
    box-shadow: 0 18px 40px rgba(0,0,0,0.45), 0 0 0 1px color-mix(in srgb, var(--dept) 30%, transparent),
        0 0 26px color-mix(in srgb, var(--dept) 28%, transparent);
}}
.igl-pcard:hover::after {{ opacity:1; }}
.igl-pcard.selected {{
    border-color: var(--dept);
    box-shadow: 0 14px 34px rgba(0,0,0,0.42), 0 0 0 1.5px var(--dept),
        0 0 28px color-mix(in srgb, var(--dept) 34%, transparent);
}}
.igl-pcard-top {{ display:flex; align-items:center; gap:12px; margin-bottom:12px; }}
.igl-pcard-ico {{
    width:46px; height:46px; border-radius:13px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center; font-size:23px;
    background: linear-gradient(135deg, color-mix(in srgb, var(--dept) 28%, transparent), color-mix(in srgb, var(--dept) 8%, transparent));
    border:1px solid color-mix(in srgb, var(--dept) 35%, transparent);
}}
.igl-pcard-dept {{ font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.08em;
    color: var(--dept); }}
.igl-pcard-name {{ font-size:17px; font-weight:800; color:{TEXT}; line-height:1.15; margin-top:1px; }}
.igl-pcard-meta {{ display:flex; align-items:center; justify-content:space-between; gap:10px;
    margin-top:6px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.07); }}
.igl-pcard-conf {{ font-size:13px; font-weight:800; color:{TEXT}; }}
.igl-pcard-conf .lbl {{ font-size:10.5px; font-weight:600; color:{TEXT_40};
    text-transform:uppercase; letter-spacing:.05em; margin-left:4px; }}
.igl-pcard-status {{ display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:700; }}
.igl-pcard-status .dot {{ width:7px; height:7px; border-radius:999px; }}
.igl-pcard-status.live {{ color:{ACCENT}; }}
.igl-pcard-status.live .dot {{ background:{ACCENT}; box-shadow:0 0 0 3px rgba(34,197,94,0.22);
    animation: igl-pulse 2.4s ease-in-out infinite; }}
.igl-pcard-status.soon {{ color:{PRIMARY_LIGHT}; }}
.igl-pcard-status.soon .dot {{ background:{PRIMARY_LIGHT}; }}
.igl-pcard-status.testing {{ color:{WARNING}; }}
.igl-pcard-status.testing .dot {{ background:{WARNING}; }}
.igl-pcard-status.draft {{ color:#94A3B8; }}
.igl-pcard-status.draft .dot {{ background:#94A3B8; }}

/* ---- AI Gateway — retry switch animation --------------------------- */
.igl-gw-switch {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap;
    margin-top:12px; padding-top:12px; border-top:1px solid {LINE}; }}
.igl-gw-keychip {{ display:inline-flex; align-items:center; gap:6px; padding:4px 11px;
    border-radius:999px; font-size:11.5px; font-weight:700;
    background: rgba(255,255,255,0.06); color:{TEXT_70}; border:1px solid {LINE}; }}
.igl-gw-keychip.from {{ opacity:.7; }}
.igl-gw-keychip.to {{ color:{PRIMARY_LIGHT}; border-color: rgba(59,130,246,0.4);
    animation: igl-pulse 1.6s ease-in-out infinite; }}
.igl-gw-keychip.ok {{ color:{ACCENT}; border-color: rgba(34,197,94,0.4); }}
.igl-gw-arrow {{ color:{TEXT_40}; font-weight:800; animation: igl-arrow-slide 1.4s ease-in-out infinite; }}

/* ---- Processor marketplace ----------------------------------------- */
.igl-mkt {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr)); gap:10px; margin:6px 0 10px; }}
.igl-mkt-item {{ display:flex; align-items:center; gap:10px; padding:11px 14px;
    border-radius: var(--radius-sm); background:{CARD}; border:1px solid {LINE};
    box-shadow: var(--shadow-sm); animation: igl-rise .4s ease both; }}
.igl-mkt-item .mk {{ width:22px; height:22px; border-radius:999px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:900; }}
.igl-mkt-item.on .mk {{ background:rgba(34,197,94,0.16); color:{ACCENT}; }}
.igl-mkt-item.soon {{ opacity:.78; }}
.igl-mkt-item.soon .mk {{ background:rgba(148,163,184,0.14); color:#94A3B8; }}
.igl-mkt-item .nm {{ font-size:13px; font-weight:600; color:{TEXT}; }}
.igl-mkt-item.soon .nm {{ color:{TEXT_70}; }}

/* ---- Department summary cards (executive dashboard) ---------------- */
.igl-deptsum {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(180px,1fr)); gap:12px; margin:6px 0 14px; }}
.igl-deptsum-card {{ --dept:{PRIMARY_LIGHT}; position:relative; display:flex; align-items:center; gap:12px;
    padding:14px 16px; border-radius: var(--radius-sm); overflow:hidden;
    background: linear-gradient(160deg, color-mix(in srgb, var(--dept) 10%, transparent), rgba(255,255,255,0.015));
    border:1px solid color-mix(in srgb, var(--dept) 24%, transparent);
    box-shadow: var(--shadow-sm); transition: transform .2s ease, box-shadow .2s ease;
    animation: igl-rise .4s ease both; }}
.igl-deptsum-card:hover {{ transform: translateY(-3px); box-shadow: var(--shadow-lift); }}
.igl-deptsum-card .ico {{ width:38px; height:38px; border-radius:11px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center; font-size:19px;
    background: color-mix(in srgb, var(--dept) 20%, transparent);
    border:1px solid color-mix(in srgb, var(--dept) 32%, transparent); }}
.igl-deptsum-card .nm {{ font-size:13.5px; font-weight:700; color:{TEXT}; line-height:1.15; }}
.igl-deptsum-card .st {{ font-size:11.5px; color:{TEXT_70}; margin-top:2px; }}
.igl-deptsum-card .st b {{ color: var(--dept); }}

/* ---- New animations ------------------------------------------------- */
@keyframes igl-count-in {{ from {{ opacity:0; transform: translateY(8px); }} to {{ opacity:1; transform:none; }} }}
@keyframes igl-arrow-slide {{ 0%,100% {{ transform: translateX(0); opacity:.55; }} 50% {{ transform: translateX(3px); opacity:1; }} }}
@keyframes igl-identity-drift {{ from {{ transform: translate3d(0,0,0); }} to {{ transform: translate3d(-1.5%,1.5%,0); }} }}
@keyframes igl-drift-a {{ from {{ transform: translate(0,0) rotate(0deg); }} to {{ transform: translate(8px,-12px) rotate(8deg); }} }}
@keyframes igl-drift-b {{ from {{ transform: translate(0,0) rotate(0deg); }} to {{ transform: translate(-10px,-8px) rotate(-6deg); }} }}
@keyframes igl-drift-c {{ from {{ transform: translate(0,0) rotate(0deg); }} to {{ transform: translate(6px,10px) rotate(5deg); }} }}

/* ---- AI Core (processing centrepiece) ------------------------------- */
.igl-core-wrap {{ display:flex; flex-direction:column; align-items:center; gap:8px; }}
.igl-core {{ position:relative; width:118px; height:118px; border-radius:50%;
    display:flex; align-items:center; justify-content:center; }}
.igl-core::before {{
    content:""; position:absolute; inset:0; border-radius:50%;
    background: conic-gradient(from 0deg, transparent 0 55%, {PRIMARY_LIGHT} 80%, {ACCENT} 95%, transparent 100%);
    -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 11px), #000 calc(100% - 10px));
    mask: radial-gradient(farthest-side, transparent calc(100% - 11px), #000 calc(100% - 10px));
    animation: igl-spin 2.8s linear infinite;
}}
.igl-core::after {{
    content:""; position:absolute; inset:0; border-radius:50%;
    border:2px solid rgba(255,255,255,0.06);
}}
.igl-core-orb {{
    width:76px; height:76px; border-radius:50%; z-index:1;
    display:flex; align-items:center; justify-content:center; font-size:30px;
    background: radial-gradient(circle at 35% 30%, {PRIMARY_LIGHT}, {PRIMARY_DARK});
    box-shadow: 0 0 28px rgba(59,130,246,0.5), inset 0 0 18px rgba(255,255,255,0.16);
    animation: igl-core-pulse 2.4s ease-in-out infinite;
}}
.igl-core-cap {{ font-size:11px; font-weight:700; letter-spacing:.10em;
    text-transform:uppercase; color:{TEXT_70}; }}

/* ---- Processing theater (live AI pipeline) -------------------------- */
.igl-theater {{
    position:relative; overflow:hidden;
    background: linear-gradient(180deg, {CARD_2}, {CARD});
    border:1px solid {LINE}; border-radius: var(--radius);
    padding: 24px 26px 20px; box-shadow: var(--shadow);
    margin: 6px 0 18px; animation: igl-rise .5s ease both;
}}
.igl-theater-head {{ display:flex; align-items:center; justify-content:space-between;
    gap:14px; flex-wrap:wrap; margin-bottom:18px; }}
.igl-theater-title {{ font-size:18px; font-weight:800; color:{TEXT}; }}
.igl-theater-sub {{ font-size:12.5px; color:{TEXT_70}; margin-top:3px; }}
.igl-theater-body {{ display:flex; gap:28px; align-items:center; flex-wrap:wrap; }}
.igl-theater-core {{ flex:0 0 auto; }}
.igl-pipe {{ flex:1 1 320px; min-width:280px; display:flex; flex-direction:column; }}

.igl-stage {{ display:flex; align-items:center; gap:12px; padding:7px 0; position:relative; }}
.igl-stage .ico {{
    width:34px; height:34px; border-radius:10px; flex-shrink:0;
    display:flex; align-items:center; justify-content:center; font-size:16px;
    background:{CARD}; border:1px solid {LINE};
    transition: background .35s ease, border-color .35s ease, box-shadow .35s ease, color .35s ease;
}}
.igl-stage .lbl {{ font-size:14px; font-weight:600; color:{TEXT_70};
    flex:0 1 auto; transition: color .3s ease; }}
.igl-stage .leader {{ flex:1 1 auto; border-bottom:1px dotted {LINE}; margin:0 2px; opacity:.55; }}
.igl-stage .state {{ font-size:13px; font-weight:800; color:{TEXT_40};
    min-width:22px; text-align:right; }}
.igl-stage::before {{
    content:""; position:absolute; left:16px; top:-7px; width:2px; height:14px;
    background:{LINE}; transition: background .35s ease;
}}
.igl-stage:first-child::before {{ display:none; }}
.igl-stage.done .ico {{ background:linear-gradient(135deg, {ACCENT}, #16A34A);
    border-color:transparent; color:#06210F; }}
.igl-stage.done .lbl {{ color:{TEXT}; }}
.igl-stage.done .state {{ color:{ACCENT}; }}
.igl-stage.done::before {{ background:{ACCENT}; }}
.igl-stage.active .ico {{ background:linear-gradient(135deg, {PRIMARY}, {PRIMARY_LIGHT});
    border-color:transparent; color:#fff; box-shadow:0 0 0 4px rgba(59,130,246,0.18);
    animation: igl-pulse 1.3s ease-in-out infinite; }}
.igl-stage.active .lbl {{ color:{TEXT}; }}
.igl-stage.active .state {{ color:{PRIMARY_LIGHT}; }}

.igl-theater-bar {{ height:8px; border-radius:999px; background:rgba(255,255,255,0.07);
    overflow:hidden; margin-top:18px; }}
.igl-theater-bar > div {{ height:100%; border-radius:999px; background-size:200% 100%;
    background-image: linear-gradient(90deg, {PRIMARY}, {PRIMARY_LIGHT}, {ACCENT});
    transition: width .45s cubic-bezier(.2,.7,.2,1); animation: igl-stripe 1s linear infinite; }}

.igl-theater-foot {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(110px,1fr));
    gap:12px 16px; margin-top:18px; padding-top:14px; border-top:1px solid {LINE}; }}
.igl-tele .k {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.06em; color:{TEXT_40}; }}
.igl-tele .v {{ font-size:14px; font-weight:700; color:{TEXT}; margin-top:2px; }}

/* success state */
.igl-theater.done-all .igl-core-orb {{ animation:none;
    background: radial-gradient(circle at 35% 30%, {ACCENT}, #15803D);
    box-shadow:0 0 30px rgba(34,197,94,0.55), inset 0 0 18px rgba(255,255,255,0.18); }}
.igl-theater.done-all .igl-core::before {{ background: conic-gradient(from 0deg, {ACCENT}, #16A34A, {ACCENT}); }}
.igl-success {{ display:flex; align-items:center; gap:12px; }}
.igl-success .ckring {{ width:54px; height:54px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    background:rgba(34,197,94,0.16); color:{ACCENT}; font-size:26px; font-weight:900;
    animation: igl-check .6s cubic-bezier(.2,.9,.3,1.4) both; }}

/* soft confetti */
.igl-confetti {{ position:absolute; top:0; left:0; right:0; height:0; pointer-events:none; }}
.igl-confetti span {{ position:absolute; top:-12px; width:8px; height:8px; border-radius:2px;
    opacity:0; animation-name: igl-confetti-fall; animation-timing-function: ease-in;
    animation-fill-mode: forwards; }}

/* confidence ring (gauge) */
.igl-ring {{ position:relative; border-radius:50%; display:flex; align-items:center;
    justify-content:center; flex-shrink:0; animation: igl-ring-in .7s ease both; }}
.igl-ring-inner {{ border-radius:50%; background:{CARD}; display:flex; align-items:center;
    justify-content:center; font-weight:800; color:{TEXT}; }}

/* respect reduced-motion preferences */
@media (prefers-reduced-motion: reduce) {{
    .igl-molecular, .igl-molecular::after, .igl-core::before, .igl-core-orb,
    .igl-theater-bar > div, .igl-confetti span,
    .igl-identity, .igl-float span, .igl-gw-keychip.to, .igl-gw-arrow,
    .igl-pcard-status.live .dot {{ animation: none !important; }}
}}

/* hide Streamlit chrome for a cleaner enterprise canvas */
#MainMenu {{ visibility:hidden; }}
footer {{ visibility:hidden; }}
</style>
"""


# ---------------------------------------------------------------------------
# Confidence helpers
# ---------------------------------------------------------------------------
def confidence_chip(score: int, band_name: str) -> str:
    """Return an HTML chip for a confidence score (green/amber/red badge)."""
    color = CONFIDENCE_COLORS.get(band_name, "#64748B")
    dot = CONFIDENCE_DOT.get(band_name, "")
    meaning = CONFIDENCE_MEANING.get(band_name, "")
    return (
        f'<span class="igl-conf-chip" style="background:{color};" '
        f'title="{meaning}">{dot} {score}%</span>'
    )


def confidence_meter(score: int, band_name: str) -> str:
    """Return an HTML confidence meter bar (animated fill, colour by band)."""
    color = CONFIDENCE_COLORS.get(band_name, "#64748B")
    pct = max(0, min(100, int(score)))
    return (
        f'<div class="igl-conf-meter"><div class="igl-conf-fill" '
        f'style="width:{pct}%;background:{color};"></div></div>'
    )


def confidence_ring(score: int, band_name: str, size: int = 64) -> str:
    """Return an HTML conic-gradient confidence gauge (ring) with the % inside.

    Args:
        score: Confidence (0–100).
        band_name: ``"high"`` / ``"review"`` / ``"verify"`` (sets the colour).
        size: Outer diameter in pixels.
    """
    color = CONFIDENCE_COLORS.get(band_name, "#64748B")
    pct = max(0, min(100, int(score)))
    inner = size - 12
    return (
        f'<div class="igl-ring" style="width:{size}px;height:{size}px;'
        f"background:conic-gradient({color} {pct * 3.6:.0f}deg, rgba(255,255,255,0.08) 0);\">"
        f'<div class="igl-ring-inner" style="width:{inner}px;height:{inner}px;'
        f'font-size:{int(size * 0.26)}px;">{pct}%</div></div>'
    )


def field_label(label: str, score: int, band_name: str) -> None:
    """Render a field label with an inline confidence chip above an input."""
    st.markdown(
        f'<div class="igl-field-label">{label} {confidence_chip(score, band_name)}</div>',
        unsafe_allow_html=True,
    )


def overall_confidence_badge(score: int, band_name: str, counts: dict[str, int] | None = None) -> None:
    """Render the prominent overall document confidence badge.

    Args:
        score: Overall confidence (0–100).
        band_name: ``"high"`` / ``"review"`` / ``"verify"``.
        counts: Optional per-band field counts for the breakdown line.
    """
    meaning = CONFIDENCE_MEANING.get(band_name, "")
    counts = counts or {}
    breakdown = (
        f'<div class="igl-overall-counts">'
        f'<span>🟢 {counts.get("high", 0)} high</span>'
        f'<span>🟡 {counts.get("review", 0)} review</span>'
        f'<span>🔴 {counts.get("verify", 0)} verify</span>'
        f"</div>"
        if counts
        else ""
    )
    st.markdown(
        f'<div class="igl-overall">'
        f"{confidence_ring(score, band_name, 64)}"
        f'<div class="igl-overall-main">'
        f'<div class="igl-overall-label">Overall Document Confidence</div>'
        f'<div class="igl-overall-value">{meaning}</div>'
        f"{breakdown}"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def lifecycle_chip(status: str) -> str:
    """Return an HTML lifecycle status chip (production/testing/draft/coming_soon)."""
    label = {
        "production": "Production",
        "testing": "Testing",
        "draft": "Draft",
        "coming_soon": "Coming Soon",
    }.get(status, status.title())
    return f'<span class="igl-life {status}">{label}</span>'


def kpi_cards(cards: list[tuple[str, str, str]]) -> None:
    """Render a responsive grid of KPI cards.

    Args:
        cards: ``(label, value, subtext)`` tuples.
    """
    html = "".join(
        f'<div class="igl-kpi"><div class="k">{k}</div>'
        f'<div class="v">{v}</div><div class="s">{s}</div></div>'
        for k, v, s in cards
    )
    st.markdown(f'<div class="igl-kpis">{html}</div>', unsafe_allow_html=True)


def glass_kpi_cards(cards: list[dict]) -> None:
    """Render a responsive grid of premium glass KPI cards.

    Each card is a dict with ``label`` and ``value`` and optional ``sub``,
    ``icon`` (emoji glyph), and ``ring`` (``{"score": int, "band": str}``) to
    show an animated confidence gauge instead of a glyph. Values animate in with
    a lightweight CSS reveal — no JavaScript.

    Args:
        cards: Card definitions (see above).
    """
    blocks = []
    for card in cards:
        ring = card.get("ring")
        if ring:
            glyph = confidence_ring(
                int(ring.get("score", 0)), ring.get("band", "high"), size=46
            )
        else:
            glyph = f'<div class="glyph">{card.get("icon", "📊")}</div>'
        sub = f'<div class="s">{card["sub"]}</div>' if card.get("sub") else ""
        blocks.append(
            f'<div class="igl-glass igl-gkpi">{glyph}'
            f'<div class="body"><div class="k">{card.get("label", "")}</div>'
            f'<div class="v">{card.get("value", "")}</div>{sub}</div></div>'
        )
    st.markdown(f'<div class="igl-gkpis">{"".join(blocks)}</div>', unsafe_allow_html=True)


def processor_card_html(
    *,
    name: str,
    dept_name: str,
    dept_key: str,
    status: str,
    accuracy: int | None = None,
    icon: str | None = None,
    selected: bool = False,
) -> str:
    """Return the HTML for one premium, selectable processor card.

    The card shows a department-tinted icon, the department label, the processor
    name, a status pill, and a confidence figure. Hover elevation/glow and the
    selected state are handled purely in CSS (see ``.igl-pcard``). Selection is
    driven by a companion Streamlit button in the caller — the card itself is a
    visual surface, keeping selection simple and reliable.

    Args:
        name: Processor (business-process) name.
        dept_name: Human-readable department label.
        dept_key: Department key used to resolve the subtle accent colour.
        status: Lifecycle status (``production`` / ``coming_soon`` / ...).
        accuracy: Optional confidence percentage to display.
        icon: Optional icon override (defaults to the department icon).
        selected: Whether this card is the active selection.

    Returns:
        An HTML string for the card.
    """
    identity = department_identity(dept_key)
    color = identity["color"]
    glyph = icon or identity["icon"]

    status_class, status_label = {
        "production": ("live", "Active"),
        "coming_soon": ("soon", "Coming Soon"),
        "testing": ("testing", "Testing"),
        "draft": ("draft", "Draft"),
    }.get(status, ("soon", status.replace("_", " ").title()))

    if accuracy is not None:
        right = f'<div class="igl-pcard-conf">{int(accuracy)}%<span class="lbl">Confidence</span></div>'
    elif status == "production":
        right = '<div class="igl-pcard-conf" style="color:rgba(255,255,255,0.5);font-size:11.5px;">Live</div>'
    else:
        right = '<div class="igl-pcard-conf" style="color:rgba(255,255,255,0.4);font-size:11.5px;">—</div>'

    selected_class = " selected" if selected else ""
    return (
        f'<div class="igl-pcard{selected_class}" style="--dept:{color};">'
        f'<div class="igl-pcard-top">'
        f'<div class="igl-pcard-ico">{glyph}</div>'
        f'<div style="min-width:0;">'
        f'<div class="igl-pcard-dept">{dept_name}</div>'
        f'<div class="igl-pcard-name">{name}</div>'
        f'</div></div>'
        f'<div class="igl-pcard-meta">'
        f'{right}'
        f'<span class="igl-pcard-status {status_class}"><span class="dot"></span>{status_label}</span>'
        f'</div>'
        f'</div>'
    )


def processor_marketplace(installed: list[str], coming_soon: list[str]) -> None:
    """Render the informational 'Installed Processors' marketplace section.

    Args:
        installed: Names of live (installed) processors.
        coming_soon: Names of declared, not-yet-built processors.
    """
    section_heading("🧩 Processor Marketplace")
    st.caption("Installed processors are live today. Coming-soon processors are on the roadmap.")
    if installed:
        st.markdown('<div class="igl-card-title">Installed</div>', unsafe_allow_html=True)
        items = "".join(
            f'<div class="igl-mkt-item on"><span class="mk">✓</span>'
            f'<span class="nm">{name}</span></div>'
            for name in installed
        )
        st.markdown(f'<div class="igl-mkt">{items}</div>', unsafe_allow_html=True)
    if coming_soon:
        st.markdown('<div class="igl-card-title">Coming Soon</div>', unsafe_allow_html=True)
        items = "".join(
            f'<div class="igl-mkt-item soon"><span class="mk">○</span>'
            f'<span class="nm">{name}</span></div>'
            for name in coming_soon
        )
        st.markdown(f'<div class="igl-mkt">{items}</div>', unsafe_allow_html=True)


def department_summary_cards(rows: list[dict]) -> None:
    """Render department summary cards tinted with each department's identity.

    Args:
        rows: Dicts with ``key``, ``name``, ``live`` (live processor count) and
            ``total`` (declared process count).
    """
    cards = []
    for row in rows:
        identity = department_identity(row.get("key", ""))
        live = int(row.get("live", 0))
        total = int(row.get("total", 0))
        cards.append(
            f'<div class="igl-deptsum-card" style="--dept:{identity["color"]};">'
            f'<div class="ico">{identity["icon"]}</div>'
            f'<div><div class="nm">{row.get("name", "")}</div>'
            f'<div class="st"><b>{live}</b> live · {total} processes</div></div>'
            f'</div>'
        )
    st.markdown(f'<div class="igl-deptsum">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_autofix_notes(notes: list[dict]) -> None:
    """Render the deterministic auto-fix corrections with their confidence."""
    if not notes:
        return
    with st.expander(f"🛠️ Auto-corrections applied: {len(notes)}", expanded=False):
        for note in notes:
            st.markdown(
                f'<div class="igl-fix">'
                f'<span>✓</span>'
                f'<span><b>{note.get("field", "")}</b></span>'
                f'<span class="old">{note.get("old", "")}</span>'
                f'<span class="arrow">→</span>'
                f'<span class="new">{note.get("new", "")}</span>'
                f'<span style="margin-left:auto;color:rgba(255,255,255,0.4);">'
                f'{note.get("confidence", "")}% · {note.get("reason", "")}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )


def coming_soon_hero(department_name: str, process_name: str) -> None:
    """Render a premium 'coming soon' hero for an unbuilt business process."""
    st.markdown(
        f'<div class="igl-soon">'
        f'<div class="glyph">🚧</div>'
        f'<div class="ttl">{process_name}</div>'
        f'<div class="sub">This processor is coming soon. The <b>{department_name}</b> '
        f"module is on the India Glycols Enterprise Document Intelligence roadmap "
        f"and will be enabled in a future release.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def confidence_legend() -> None:
    """Render a compact legend explaining the confidence colours."""
    items = "".join(
        f'<span>{CONFIDENCE_DOT[b]} <b>{CONFIDENCE_MEANING[b]}</b></span>'
        for b in ("high", "review", "verify")
    )
    ranges = (
        '<span style="color:rgba(255,255,255,0.40);">95–100 · 75–94 · 0–74</span>'
    )
    st.markdown(
        f'<div class="igl-legend">{items}{ranges}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Header & navigation
# ---------------------------------------------------------------------------
def render_header(assets_dir: Path) -> None:
    """Render the branded India Glycols application header.

    Args:
        assets_dir: Directory to look for the corporate logo in.
    """
    logo_path = find_logo(assets_dir)
    if logo_path is not None:
        logo_block = _logo_html(logo_path)
    else:
        logo_block = (
            '<div class="igl-logo" style="display:flex;align-items:center;'
            'justify-content:center;color:#0F4C95;font-weight:900;font-size:22px;">IGL</div>'
        )

    st.markdown(
        f"""
        <div class="igl-header">
            {logo_block}
            <div class="igl-head-text">
                <div class="igl-wordmark">India <span class="igl-accent">Glycols</span> Limited</div>
                <div class="igl-sub">{PLATFORM_NAME}</div>
                <div class="igl-head-badges">
                    <span class="igl-tag">Version 2.0</span>
                    <span class="igl-tag"><span class="dot"></span>Production Ready</span>
                    <span class="igl-tag"><span class="dot"></span>AI Gateway Online</span>
                    <span class="igl-tag">{TAGLINE}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand(assets_dir: Path) -> None:
    """Render the compact brand lockup at the top of the sidebar."""
    logo_path = find_logo(assets_dir)
    if logo_path is not None:
        logo_block = _logo_html(logo_path, css_class="igl-side-logo")
    else:
        logo_block = (
            '<div class="igl-side-logo" style="display:flex;align-items:center;'
            'justify-content:center;color:#0F4C95;font-weight:900;font-size:13px;">IGL</div>'
        )
    st.markdown(
        f"""
        <div class="igl-side-brand">
            {logo_block}
            <div>
                <div class="igl-side-name">India Glycols</div>
                <div class="igl-side-sub">Document Intelligence</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_breadcrumb(department_name: str, use_case_name: str | None = None) -> None:
    """Render a small breadcrumb showing the current navigation context."""
    trail = f"<span>{department_name}</span>"
    if use_case_name:
        trail += f'<span class="sep">›</span><span>{use_case_name}</span>'
    st.markdown(
        f'<div class="igl-crumb">📍 {trail}</div>',
        unsafe_allow_html=True,
    )


def section_heading(title: str) -> None:
    """Render a premium section heading with an accent bar."""
    st.markdown(
        f'<div class="igl-section"><span class="bar"></span>{title}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# AI Gateway dashboard card
# ---------------------------------------------------------------------------
def render_gateway_status(
    status: dict,
    queue: int = 0,
    stage: str = "Idle",
) -> None:
    """Render the AI Gateway status as a clean enterprise dashboard card.

    Shows gateway health, current model, current API key number (by number
    only — never the key value), retry count, queue size, and the current
    processing stage from the most recent AI request. When the most recent
    request needed failover, an animated "Key 1 → Key N → Success" switch is
    shown to visualize the gateway recovering.

    Args:
        status: A snapshot from ``AIGateway.status()`` containing ``model``,
            ``key_number``, ``total_keys``, ``retries``, ``cycle``, and
            ``healthy``.
        queue: Documents currently waiting in the processing queue.
        stage: Human-readable current processing stage.
    """
    healthy = bool(status.get("healthy"))
    model = str(status.get("model") or "—")
    key_number = int(status.get("key_number", 0))
    total = int(status.get("total_keys", 0))
    retries = int(status.get("retries", 0))

    if not healthy:
        label, color = "Offline", ERROR
    elif retries > 0:
        label, color = "Recovered", WARNING
    else:
        label, color = "Healthy", ACCENT

    key_txt = f"Key {key_number}" if key_number else "—"

    # When the last request rotated keys, visualize the failover sequence.
    switch = ""
    if retries > 0 and key_number:
        switch = (
            '<div class="igl-gw-switch">'
            '<span class="igl-gw-keychip from">Key 1</span>'
            '<span class="igl-gw-arrow">→</span>'
            f'<span class="igl-gw-keychip to">Key {key_number}</span>'
            '<span class="igl-gw-arrow">→</span>'
            '<span class="igl-gw-keychip ok">✓ Success</span>'
            '</div>'
        )

    st.markdown(
        f"""
        <div class="igl-gw">
            <div class="igl-gw-top">
                <span class="igl-gw-title">AI Gateway</span>
                <span class="igl-status-pill" style="background:rgba(255,255,255,0.06);color:{color};">
                    <span class="dot" style="background:{color};box-shadow:0 0 0 3px {color}33;"></span>{label}
                </span>
            </div>
            <div class="igl-gw-grid">
                <div class="igl-gw-cell"><div class="k">Model</div><div class="v">{model}</div></div>
                <div class="igl-gw-cell"><div class="k">API Key</div><div class="v">{key_txt} / {total}</div></div>
                <div class="igl-gw-cell"><div class="k">Retry Count</div><div class="v">{retries}</div></div>
                <div class="igl-gw-cell"><div class="k">Queue Size</div><div class="v">{queue}</div></div>
                <div class="igl-gw-cell"><div class="k">Stage</div><div class="v">{stage}</div></div>
                <div class="igl-gw-cell"><div class="k">Failover</div><div class="v">Key + Model</div></div>
            </div>
            {switch}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Premium processing experience — live "AI pipeline" theater
# ---------------------------------------------------------------------------
def _fmt_secs(seconds: float) -> str:
    """Format a duration as a compact ``12s`` / ``1m 05s`` string."""
    seconds = max(float(seconds), 0.0)
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(round(seconds)), 60)
    return f"{minutes}m {secs:02d}s"


_CONFETTI_COLORS = (PRIMARY_LIGHT, ACCENT, WARNING, "#2BB0C9", "#A78BFA")


def _confetti_html(pieces: int = 16) -> str:
    """Build a handful of lightweight, CSS-animated confetti pieces."""
    spans = []
    for _ in range(pieces):
        left = random.randint(2, 98)
        color = random.choice(_CONFETTI_COLORS)
        delay = random.uniform(0, 0.5)
        dur = random.uniform(1.4, 2.2)
        spans.append(
            f'<span style="left:{left}%;background:{color};'
            f"animation-delay:{delay:.2f}s;animation-duration:{dur:.2f}s;\"></span>"
        )
    return f'<div class="igl-confetti">{"".join(spans)}</div>'


class ProcessingTheater:
    """Live "AI pipeline" processing experience (replaces a plain spinner).

    Renders a rotating AI Core, an illuminating stage pipeline
    (OCR → AI Understanding → Field Extraction → Validation → Confidence →
    Excel), a gradient progress bar, and live telemetry (document counter,
    elapsed / estimated remaining, active model, active key number, gateway
    health). It is driven entirely by ``processing.process_batch`` progress
    callbacks and is pure CSS/SVG, so it stays light and never slows
    processing.

    Usage::

        theater = ui.ProcessingTheater(total=len(docs), gateway=gw_status)
        process_batch(..., progress_cb=theater.update)
        theater.finish()
    """

    #: (phase key, glyph, label) in top-to-bottom display order. Labels narrate
    #: the molecules-become-data story (Document → Atoms → Molecules →
    #: Scientific Network → AI Core → Structured Business Data → Excel); the
    #: phase keys stay aligned to the backend pipeline so behaviour is unchanged.
    STAGES = (
        ("ocr", "📄", "Document → Atoms"),
        ("ai", "⚛️", "Atoms → Molecules"),
        ("extraction", "🕸️", "Scientific Network"),
        ("validation", "🧠", "AI Core"),
        ("confidence", "📊", "Structured Business Data"),
        ("excel", "📗", "Excel"),
    )
    #: per-document phases emitted by ``extract_document`` (in display order).
    _PHASE_ORDER = ("ocr", "ai", "extraction", "validation", "confidence")

    def __init__(self, total: int, gateway: dict | None = None) -> None:
        self.total = max(int(total), 1)
        self.placeholder = st.empty()
        self.start = time.perf_counter()
        self.completed = 0
        self.current = 0
        self.current_name = "—"
        self.fraction = 0.0
        gateway = gateway or {}
        self.model = str(gateway.get("model") or "—")
        self.key_number = int(gateway.get("key_number", 0) or 0)
        self.healthy = bool(gateway.get("healthy", True))
        self._stages = {key: "pending" for key, _, _ in self.STAGES}

    # -- state ---------------------------------------------------------- #
    def _reset_stages(self) -> None:
        for key in self._stages:
            self._stages[key] = "pending"

    def update(self, done: float, total: int, doc, phase: str) -> None:
        """Progress callback: advance the pipeline and re-render.

        Signature matches ``processing.ProgressCallback``.
        """
        self.total = max(int(total), 1)
        if phase == "classifying":
            self.current = int(done) + 1
            self.current_name = getattr(doc, "filename", "—")
            self._reset_stages()
        elif phase in self._PHASE_ORDER:
            idx = self._PHASE_ORDER.index(phase)
            for prior in self._PHASE_ORDER[:idx]:
                self._stages[prior] = "done"
            self._stages[phase] = "active"
        elif phase == "done":
            for key in self._PHASE_ORDER:
                self._stages[key] = "done"
            self.completed += 1
        self.fraction = min(max(done / self.total, 0.0), 1.0)
        self._render()

    def finish(self) -> None:
        """Render the celebratory 'ready to download' completion state."""
        for key in self._stages:
            self._stages[key] = "done"
        self.completed = self.total
        self.fraction = 1.0
        self._render(success=True)

    # -- rendering ------------------------------------------------------ #
    def _eta(self) -> str:
        elapsed = time.perf_counter() - self.start
        if self.completed <= 0:
            return "Calculating…"
        per = elapsed / self.completed
        return _fmt_secs(per * max(self.total - self.completed, 0))

    def _stages_html(self) -> str:
        out = []
        for key, icon, label in self.STAGES:
            state = self._stages[key]
            cls = state if state in ("active", "done") else ""
            mark = "✓" if state == "done" else ("…" if state == "active" else "")
            out.append(
                f'<div class="igl-stage {cls}">'
                f'<div class="ico">{icon}</div>'
                f'<div class="lbl">{label}</div>'
                f'<div class="leader"></div>'
                f'<div class="state">{mark}</div>'
                f"</div>"
            )
        return "".join(out)

    def _telemetry_html(self) -> str:
        gw_label = "Online" if self.healthy else "Offline"
        gw_color = ACCENT if self.healthy else ERROR
        key_txt = f"#{self.key_number}" if self.key_number else "—"
        cells = [
            ("Document", f"{min(self.current, self.total)} / {self.total}"),
            ("Completed", f"{self.completed} / {self.total}"),
            ("Elapsed", _fmt_secs(time.perf_counter() - self.start)),
            ("Est. remaining", self._eta()),
            ("AI Model", self.model),
            ("Active Key", key_txt),
        ]
        body = "".join(
            f'<div class="igl-tele"><div class="k">{k}</div><div class="v">{v}</div></div>'
            for k, v in cells
        )
        body += (
            f'<div class="igl-tele"><div class="k">Gateway</div>'
            f'<div class="v" style="color:{gw_color};">{gw_label}</div></div>'
        )
        return body

    def _render(self, success: bool = False) -> None:
        pct = int(round(self.fraction * 100))
        if success:
            title = "Excel Ready"
            sub = "Structured business data is ready — download your Excel below."
            extra = "done-all"
            confetti = _confetti_html()
            badge = '<div class="igl-success"><div class="ckring">✓</div></div>'
        else:
            title = "AI Processing Pipeline"
            sub = f"Processing <b>{self.current_name}</b>"
            extra = ""
            confetti = ""
            badge = ""
        core = (
            '<div class="igl-core-wrap"><div class="igl-core">'
            '<div class="igl-core-orb">🧬</div></div>'
            '<div class="igl-core-cap">AI Core</div></div>'
        )
        html = (
            f'<div class="igl-theater {extra}">{confetti}'
            f'<div class="igl-theater-head">'
            f'<div><div class="igl-theater-title">{title}</div>'
            f'<div class="igl-theater-sub">{sub}</div></div>'
            f"{badge}</div>"
            f'<div class="igl-theater-body">'
            f'<div class="igl-theater-core">{core}</div>'
            f'<div class="igl-pipe">{self._stages_html()}</div>'
            f"</div>"
            f'<div class="igl-theater-bar"><div style="width:{pct}%;"></div></div>'
            f'<div class="igl-theater-foot">{self._telemetry_html()}</div>'
            f"</div>"
        )
        self.placeholder.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Status helpers (document tabs / queue)
# ---------------------------------------------------------------------------
def status_icon(status: str) -> str:
    """Return the glyph used to represent a document processing status."""
    return {
        "done": "✅",
        "unsupported": "🚫",
        "error": "⚠️",
    }.get(status, "⏳")


def render_coming_soon(department_name: str, use_case_name: str) -> None:
    """Render a professional placeholder for not-yet-built use cases."""
    st.subheader(f"{department_name}  ›  {use_case_name}")
    st.info("This document processor is coming soon.")
    st.caption(
        "This module is part of the India Glycols Enterprise Document "
        "Intelligence Platform roadmap and will be enabled in a future release."
    )
