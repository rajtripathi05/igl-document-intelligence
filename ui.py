"""Presentation helpers: India Glycols branding, theming, and header.

Keeps visual/branding concerns out of ``app.py``. The logo is auto-detected
from the ``assets/`` directory so a logo file can be dropped in without code
changes.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# India Glycols corporate palette (professional blue/teal accents).
PRIMARY = "#0B5394"
PRIMARY_DARK = "#073763"
ACCENT = "#1AA179"
COMPANY_NAME = "India Glycols Limited"
PLATFORM_NAME = "Enterprise Document Intelligence Platform"

# Subtle, enterprise-friendly confidence colours (muted, not flashy).
CONFIDENCE_COLORS = {
    "high": "#1f7a4d",     # green   95-100%  High Confidence
    "review": "#9a7d1a",   # amber   70-94%   Needs Review
    "verify": "#9b3b3b",   # red     0-69%    Manual Verification Recommended
}
CONFIDENCE_DOT = {"high": "🟢", "review": "🟡", "verify": "🔴"}
CONFIDENCE_MEANING = {
    "high": "High Confidence",
    "review": "Needs Review",
    "verify": "Manual Verification Recommended",
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


def _logo_html(logo_path: Path) -> str:
    """Build an inline-image HTML snippet for the given logo file."""
    data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    suffix = logo_path.suffix.lower().lstrip(".")
    mime = "svg+xml" if suffix == "svg" else suffix
    return (
        f'<img src="data:image/{mime};base64,{data}" '
        f'alt="{COMPANY_NAME}" class="igl-logo" />'
    )


def inject_theme() -> None:
    """Inject global CSS for a clean, professional corporate look."""
    st.markdown(
        f"""
        <style>
        .stApp {{ background: #0d1117; }}
        .igl-header {{
            display: flex; align-items: center; gap: 18px;
            padding: 18px 24px; border-radius: 14px;
            background: linear-gradient(135deg, {PRIMARY_DARK}, {PRIMARY});
            box-shadow: 0 6px 24px rgba(0,0,0,0.35);
            margin-bottom: 8px;
        }}
        .igl-logo {{ height: 56px; width: auto; border-radius: 8px; background: #fff; padding: 6px; }}
        .igl-wordmark {{ font-size: 30px; font-weight: 800; color: #fff; line-height: 1.1; }}
        .igl-accent {{ color: {ACCENT}; }}
        .igl-sub {{ font-size: 14px; color: #cfd8e3; margin-top: 2px; }}
        .igl-tag {{
            display:inline-block; margin-top:6px; padding:2px 10px; border-radius:999px;
            background: rgba(255,255,255,0.12); color:#e8eef5; font-size:12px; font-weight:600;
        }}
        .igl-crumb {{
            color:#9fb3c8; font-size:13px; margin: 10px 0 4px;
        }}
        .stButton>button[kind="primary"] {{
            background: {PRIMARY}; border: none; font-weight:600;
        }}
        /* SAP-Fiori-style cards and chips. */
        .igl-card {{
            background: #161b22; border: 1px solid #2a3441; border-radius: 12px;
            padding: 14px 16px; margin-bottom: 10px;
        }}
        .igl-card-title {{ font-size: 13px; color:#9fb3c8; font-weight:600;
            text-transform: uppercase; letter-spacing: .04em; margin-bottom: 6px; }}
        .igl-conf-chip {{
            display:inline-block; padding:1px 9px; border-radius:999px;
            font-size:11px; font-weight:700; color:#fff;
        }}
        .igl-field-label {{ display:flex; align-items:center; gap:8px;
            font-size:13px; color:#c7d2de; margin-bottom:-6px; }}
        .igl-doc-tab {{ font-weight:600; }}
        .igl-metric {{ font-size:26px; font-weight:800; color:#fff; }}
        .igl-metric-label {{ font-size:12px; color:#9fb3c8; }}
        section[data-testid="stSidebar"] {{ background:#0a1018; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def confidence_chip(score: int, band_name: str) -> str:
    """Return an HTML chip for a confidence score (subtle enterprise styling)."""
    color = CONFIDENCE_COLORS.get(band_name, "#555")
    dot = CONFIDENCE_DOT.get(band_name, "")
    return (
        f'<span class="igl-conf-chip" style="background:{color};">'
        f"{dot} {score}%</span>"
    )


def field_label(label: str, score: int, band_name: str) -> None:
    """Render a field label with an inline confidence chip above an input."""
    st.markdown(
        f'<div class="igl-field-label">{label} {confidence_chip(score, band_name)}</div>',
        unsafe_allow_html=True,
    )


def confidence_legend() -> None:
    """Render a compact legend explaining the confidence colours."""
    parts = [
        f"{CONFIDENCE_DOT[b]} {CONFIDENCE_MEANING[b]}"
        for b in ("high", "review", "verify")
    ]
    st.caption("  ·  ".join(parts))


def render_header(assets_dir: Path) -> None:
    """Render the branded India Glycols application header.

    Args:
        assets_dir: Directory to look for the corporate logo in.
    """
    logo_path = find_logo(assets_dir)
    if logo_path is not None:
        logo_block = _logo_html(logo_path)
    else:
        # Fallback monogram until a logo file is added to assets/.
        logo_block = '<div class="igl-logo" style="display:flex;align-items:center;justify-content:center;color:#0B5394;font-weight:900;font-size:24px;">IGL</div>'

    st.markdown(
        f"""
        <div class="igl-header">
            {logo_block}
            <div>
                <div class="igl-wordmark">India <span class="igl-accent">Glycols</span> Limited</div>
                <div class="igl-sub">{PLATFORM_NAME}</div>
                <span class="igl-tag">Version 1.2 · AI-Powered Document Processing</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_breadcrumb(department_name: str, use_case_name: str | None = None) -> None:
    """Render a small breadcrumb showing the current navigation context."""
    trail = f"{department_name}"
    if use_case_name:
        trail += f"  ›  {use_case_name}"
    st.markdown(f'<div class="igl-crumb">📍 {trail}</div>', unsafe_allow_html=True)


def render_key_status(status: dict) -> None:
    """Render the development-only Gemini key status indicator.

    Shows the active key number, total keys, and health — never key values.

    Args:
        status: A snapshot from ``GeminiKeyManager.status()`` containing
            ``active_number``, ``total``, ``available``, and ``healthy``.
    """
    healthy = bool(status.get("healthy"))
    available = int(status.get("available", 0))
    total = int(status.get("total", 0))
    active = int(status.get("active_number", 0))

    if not healthy:
        label, color = "Rate-limited", CONFIDENCE_COLORS["verify"]
    elif available < total:
        label, color = "Degraded", CONFIDENCE_COLORS["review"]
    else:
        label, color = "Healthy", CONFIDENCE_COLORS["high"]

    st.markdown(
        f'<div class="igl-card-title">Gemini Key</div>'
        f'<div class="igl-metric">#{active} / {total}</div>'
        f'<div style="margin-top:4px;">'
        f'<span class="igl-conf-chip" style="background:{color};">{label}</span>'
        f'  <span class="igl-metric-label">{available} available</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_coming_soon(department_name: str, use_case_name: str) -> None:
    """Render a professional placeholder for not-yet-built use cases."""
    st.subheader(f"{department_name}  ›  {use_case_name}")
    st.info("This document processor is coming soon.")
    st.caption(
        "This module is part of the India Glycols Enterprise Document "
        "Intelligence Platform roadmap and will be enabled in a future release."
    )
