"""Google Gemini provider (single key) behind the provider-agnostic gateway.

Wraps the ``google-genai`` SDK. Keys are supplied by the factory/gateway, never
read here from the environment beyond the single configured value. Failures are
classified into transient vs. fatal via :mod:`gemini_errors` (message/status
based, SDK-version tolerant).
"""

from __future__ import annotations

import logging
from typing import Any

from gemini_errors import is_fatal_error
from providers.base import FatalAIError, Provider, ProviderResponse, TransientAIError

logger = logging.getLogger(__name__)


class GeminiProvider(Provider):
    """Provider backed by Google Gemini via the ``google-genai`` SDK."""

    name = "gemini"

    def __init__(self, api_key: str | None) -> None:
        """Initialize with a single API key (may be empty when unconfigured)."""
        self._api_key = (api_key or "").strip()

    @property
    def has_key(self) -> bool:
        """True if a Gemini API key is configured."""
        return bool(self._api_key)

    def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        instruction: str,
        parts: list[tuple[bytes, str]],
        json_mode: bool = True,
    ) -> ProviderResponse:
        """Run one Gemini request and normalize the response."""
        from google import genai
        from google.genai import types

        document_parts = [
            types.Part.from_bytes(data=data, mime_type=mime) for data, mime in parts
        ]
        config_kwargs: dict[str, Any] = {"temperature": 0.0}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"

        try:
            client = genai.Client(api_key=self._api_key)
            response = client.models.generate_content(
                model=model,
                contents=[instruction, *document_parts],
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:  # noqa: BLE001 - classify then re-raise typed
            if is_fatal_error(exc):
                raise FatalAIError(str(exc)) from exc
            raise TransientAIError(str(exc)) from exc

        text = getattr(response, "text", None) or ""
        if not text:
            # An empty completion is treated as transient (worth a retry/escalation).
            raise TransientAIError("Gemini returned no text output.")
        return ProviderResponse(text=text, usage=_usage(response), model=model)


def _usage(response: Any) -> dict[str, int]:
    """Extract token usage from a Gemini response (best-effort)."""
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    input_tokens = int(getattr(meta, "prompt_token_count", 0) or 0)
    output_tokens = int(getattr(meta, "candidates_token_count", 0) or 0)
    total = int(getattr(meta, "total_token_count", 0) or (input_tokens + output_tokens))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
    }
