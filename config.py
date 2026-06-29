"""Application configuration.

Environment variables are loaded from a local ``.env`` file when present.
Secrets must never be hardcoded in source files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from ai_gateway import AIGateway, discover_models
from api_key_manager import GeminiKeyManager


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


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
