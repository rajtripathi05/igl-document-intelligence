"""Provider selection from environment configuration.

The active provider and the DEFAULT/RETRY models are chosen entirely from
``.env`` — the rest of the platform never branches on provider identity:

    AI_PROVIDER=openrouter          # or: gemini  (future: claude, openai, ...)
    AI_API_KEY=<single key>
    DEFAULT_MODEL=google/gemini-flash-latest
    RETRY_MODEL=google/gemini-pro-latest

Adding a new provider is a new :class:`~providers.base.Provider` subclass plus a
one-line entry in :data:`_PROVIDERS` — no changes to processors, the engine, or
the gateway.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from providers.base import Provider
from providers.gemini import GeminiProvider
from providers.openrouter import OpenRouterProvider

logger = logging.getLogger(__name__)

#: Registry of known providers: name -> (factory, default_model, retry_model).
_PROVIDERS: dict[str, tuple[type[Provider], str, str]] = {
    "openrouter": (
        OpenRouterProvider,
        "google/gemini-flash-latest",
        "google/gemini-pro-latest",
    ),
    "gemini": (GeminiProvider, "gemini-2.5-flash", "gemini-2.5-pro"),
}

_DEFAULT_PROVIDER = "openrouter"
_NUMBERED_GEMINI_KEY_RE = re.compile(r"^GEMINI_API_KEY_(\d+)$")


@dataclass(frozen=True)
class ProviderConfig:
    """Resolved provider + model policy from the environment."""

    provider: Provider
    provider_name: str
    default_model: str
    retry_model: str


def _first_gemini_key() -> str:
    """Return the first configured legacy Gemini key, or an empty string.

    Enables running (and verifying) the platform on the retained Gemini provider
    using an existing ``GEMINI_API_KEY_*`` when ``AI_API_KEY`` is not yet set —
    e.g. before an OpenRouter key is provisioned.
    """
    numbered: list[tuple[int, str]] = []
    for name, value in os.environ.items():
        match = _NUMBERED_GEMINI_KEY_RE.match(name)
        if match and value and value.strip():
            numbered.append((int(match.group(1)), value.strip()))
    numbered.sort(key=lambda item: item[0])
    if numbered:
        return numbered[0][1]
    bare = os.getenv("GEMINI_API_KEY", "")
    return bare.strip()


def build_provider() -> ProviderConfig:
    """Build the configured provider and resolve the DEFAULT/RETRY models."""
    name = (os.getenv("AI_PROVIDER") or _DEFAULT_PROVIDER).strip().lower()
    if name not in _PROVIDERS:
        logger.warning(
            "Unknown AI_PROVIDER '%s'; falling back to '%s'.", name, _DEFAULT_PROVIDER
        )
        name = _DEFAULT_PROVIDER

    provider_cls, default_model_fallback, retry_model_fallback = _PROVIDERS[name]

    api_key = (os.getenv("AI_API_KEY") or "").strip()
    # Convenience fallback: the retained Gemini provider can use an existing
    # GEMINI_API_KEY_* when AI_API_KEY is unset (testing / pre-OpenRouter).
    if not api_key and name == "gemini":
        api_key = _first_gemini_key()

    default_model = (os.getenv("DEFAULT_MODEL") or "").strip() or default_model_fallback
    retry_model = (os.getenv("RETRY_MODEL") or "").strip() or retry_model_fallback

    provider = provider_cls(api_key)
    logger.info(
        "AI provider '%s' initialized (default=%s, retry=%s, key=%s).",
        name,
        default_model,
        retry_model,
        "present" if provider.has_key else "MISSING",
    )
    return ProviderConfig(
        provider=provider,
        provider_name=name,
        default_model=default_model,
        retry_model=retry_model,
    )
