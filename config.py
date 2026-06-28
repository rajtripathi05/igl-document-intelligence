"""Application configuration.

Environment variables are loaded from a local ``.env`` file when present.
Secrets must never be hardcoded in source files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    prompts_dir: Path = BASE_DIR / "prompts"
    schemas_dir: Path = BASE_DIR / "schemas"
    templates_dir: Path = BASE_DIR / "templates"
    samples_dir: Path = BASE_DIR / "samples"
    outputs_dir: Path = BASE_DIR / "outputs"
    assets_dir: Path = BASE_DIR / "assets"

    @property
    def system_prompt_path(self) -> Path:
        """Path to the system prompt file."""
        return self.prompts_dir / "system_prompt.txt"

    @property
    def extraction_prompt_path(self) -> Path:
        """Path to the extraction prompt file."""
        return self.prompts_dir / "extraction_prompt.txt"

    @property
    def schema_path(self) -> Path:
        """Path to the canonical Purchase Order JSON schema."""
        return self.schemas_dir / "purchase_order_schema.json"

    # ----- Generic, document-type-agnostic path helpers ------------------ #

    def prompt_path(self, filename: str) -> Path:
        """Return the path to a prompt file in the prompts directory."""
        return self.prompts_dir / filename

    def schema_path_for(self, filename: str) -> Path:
        """Return the path to a schema file in the schemas directory."""
        return self.schemas_dir / filename

    # ----- Shipping Bill paths ------------------------------------------- #

    @property
    def shipping_bill_system_prompt_path(self) -> Path:
        """Path to the Shipping Bill system prompt file."""
        return self.prompts_dir / "shipping_bill_system_prompt.txt"

    @property
    def shipping_bill_extraction_prompt_path(self) -> Path:
        """Path to the Shipping Bill extraction prompt file."""
        return self.prompts_dir / "shipping_bill_extraction_prompt.txt"

    @property
    def shipping_bill_schema_path(self) -> Path:
        """Path to the canonical Shipping Bill JSON schema."""
        return self.schemas_dir / "shipping_bill_schema.json"


settings = Settings()
