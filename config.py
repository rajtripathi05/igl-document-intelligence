"""Application configuration.

Environment variables are loaded from a local ``.env`` file when present.
Secrets must never be hardcoded in source files.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from ai_gateway import AIGateway, discover_models
from api_key_manager import GeminiKeyManager


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

#: Default Developer Mode password used only when no admin password is provided
#: via the environment or Streamlit secrets. The value is never rendered in the
#: UI — it is only ever compared against, in constant time.
_DEFAULT_ADMIN_PASSWORD = "IGL@2006"
#: Environment variables consulted (in order) for the Developer Mode password.
_ADMIN_PASSWORD_ENV_VARS = ("IGL_ADMIN_PASSWORD", "ADMIN_PASSWORD", "DEV_MODE_PASSWORD")
#: Keys consulted (in order) inside Streamlit secrets for the same password.
_ADMIN_PASSWORD_SECRET_KEYS = ("admin_password", "IGL_ADMIN_PASSWORD", "dev_mode_password")


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    # Backward-compatible default model. The gateway discovers the full,
    # configurable model priority list (GEMINI_MODEL_1..N); this single value is
    # retained only for callers/tests that still ask for a default model. Models
    # are never hardcoded inside the extraction engine — see ``ai_gateway``.
    gemini_model: str = discover_models()[0]
    # Development mode enables the non-sensitive Gemini key status indicator in
    # the UI. Defaults to on; set APP_ENV=production (or DEV_MODE=false) to hide.
    dev_mode: bool = os.getenv("APP_ENV", "development").lower() != "production" and (
        os.getenv("DEV_MODE", "true").lower() not in ("0", "false", "no")
    )
    # V2.0: prompts/schemas/templates/samples are owned per-processor under
    # processors/<key>/, discovered from manifests. Only app-level directories
    # remain here.
    outputs_dir: Path = BASE_DIR / "outputs"
    assets_dir: Path = BASE_DIR / "assets"


settings = Settings()


# Single shared Gemini key manager for the whole application. Modules obtain
# keys exclusively through this manager and never read key env vars directly.
gemini_key_manager = GeminiKeyManager()


# Single shared Enterprise AI Gateway — the only entry point for AI requests.
# Every processor and the classifier route Gemini calls through this instance so
# key + model failover is applied uniformly. No module talks to Gemini directly.
ai_gateway = AIGateway(key_manager=gemini_key_manager)


def has_gemini_keys() -> bool:
    """True if at least one Gemini API key is configured."""
    return gemini_key_manager.has_keys()


def _admin_password() -> str:
    """Resolve the Developer Mode password from configuration.

    Resolution order (first match wins):
        1. Environment variables (``IGL_ADMIN_PASSWORD`` / ``ADMIN_PASSWORD`` /
           ``DEV_MODE_PASSWORD``).
        2. Streamlit secrets (``admin_password`` / ``IGL_ADMIN_PASSWORD`` /
           ``dev_mode_password``), if a secrets file is present.
        3. The built-in default (``IGL@2006``).

    The resolved value is never logged or displayed — it is only ever compared
    against a candidate, in constant time (see :func:`verify_admin_password`).
    """
    for name in _ADMIN_PASSWORD_ENV_VARS:
        value = os.getenv(name)
        if value:
            return value

    # Streamlit secrets are optional; accessing them with no secrets file raises.
    try:  # pragma: no cover - depends on a runtime secrets file
        import streamlit as st

        for key in _ADMIN_PASSWORD_SECRET_KEYS:
            secret = st.secrets.get(key)  # type: ignore[attr-defined]
            if secret:
                return str(secret)
    except Exception:  # noqa: BLE001 - no secrets configured is a normal case
        pass

    return _DEFAULT_ADMIN_PASSWORD


def verify_admin_password(candidate: str) -> bool:
    """Return True if ``candidate`` matches the configured Developer Mode password.

    Uses a constant-time comparison so the check does not leak the password
    length or contents through timing. The configured password is never exposed
    by this function under any circumstance.

    Args:
        candidate: The password entered by the user.

    Returns:
        True only when the candidate exactly matches the configured password.
    """
    if not candidate:
        return False
    return hmac.compare_digest(str(candidate), _admin_password())
