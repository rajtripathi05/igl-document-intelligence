"""Presentation helpers: India Glycols branding, theming, and header.

Design language: ~70% SAP Fiori, ~30% Apple Human Interface — a clean, spacious,
premium enterprise look. All visual/branding concerns live here so ``app.py`` and
``engine.py`` stay focused on orchestration and the generic engine.

The logo is auto-detected from the ``assets/`` directory, so a logo file can be
dropped in without code changes.
"""

from __future__ import annotations

import base64
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
    "review": WARNING,   # amber   70-94%   Needs Review
    "verify": ERROR,     # red     0-69%    Manual Verification
}
CONFIDENCE_DOT = {"high": "🟢", "review": "🟡", "verify": "🔴"}
CONFIDENCE_MEANING = {
    "high": "Excellent",
    "review": "Needs Review",
    "verify": "Manual Verification",
}

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


def field_label(label: str, score: int, band_name: str) -> None:
    """Render a field label with an inline confidence chip above an input."""
    st.markdown(
        f'<div class="igl-field-label">{label} {confidence_chip(score, band_name)}</div>',
        unsafe_allow_html=True,
    )


def confidence_legend() -> None:
    """Render a compact legend explaining the confidence colours."""
    items = "".join(
        f'<span>{CONFIDENCE_DOT[b]} <b>{CONFIDENCE_MEANING[b]}</b></span>'
        for b in ("high", "review", "verify")
    )
    ranges = (
        '<span style="color:rgba(255,255,255,0.40);">95–100 · 70–94 · 0–69</span>'
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
                    <span class="igl-tag">Version 1.2</span>
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
def render_gateway_status(status: dict) -> None:
    """Render the AI Gateway status as a clean enterprise dashboard card.

    Shows the current model, active key number / total, retry count, and gateway
    health from the most recent AI request — never key values.

    Args:
        status: A snapshot from ``AIGateway.status()`` containing ``model``,
            ``key_number``, ``total_keys``, ``retries``, ``cycle``, and
            ``healthy``.
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
        label, color = "Online", ACCENT

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
                <div class="igl-gw-cell"><div class="k">Active Key</div><div class="v">{key_number} / {total}</div></div>
                <div class="igl-gw-cell"><div class="k">Retries</div><div class="v">{retries}</div></div>
                <div class="igl-gw-cell"><div class="k">Failover</div><div class="v">Key + Model</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
