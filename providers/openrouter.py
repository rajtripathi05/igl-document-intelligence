"""OpenRouter provider — the platform's default AI backend.

OpenRouter exposes an OpenAI-compatible Chat Completions API that fronts many
model families (``google/gemini-*``, ``anthropic/claude-*``, ``openai/*``,
``deepseek/*``, ``qwen/*``, ...). Selecting any of them is a ``DEFAULT_MODEL`` /
``RETRY_MODEL`` change in ``.env`` — no code change.

Documents are sent as inline image ``data:`` URLs (PDF pages are rasterized to
images first via :mod:`providers._images`). Token usage is read from the
standard ``usage`` block. The API key is sent only in the ``Authorization``
header and never logged or placed in an exception.
"""

from __future__ import annotations

import logging
from typing import Any

from providers._images import parts_to_image_urls
from providers.base import FatalAIError, Provider, ProviderResponse, TransientAIError

logger = logging.getLogger(__name__)

_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
#: HTTP statuses worth retrying (rate limit, request timeout, server errors).
_TRANSIENT_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
#: Request timeout (seconds) — vision requests over several pages can be slow.
_TIMEOUT_SECONDS = 180.0


class OpenRouterProvider(Provider):
    """Provider backed by OpenRouter's OpenAI-compatible Chat Completions API."""

    name = "openrouter"

    def __init__(self, api_key: str | None) -> None:
        """Initialize with a single OpenRouter API key (may be empty)."""
        self._api_key = (api_key or "").strip()

    @property
    def has_key(self) -> bool:
        """True if an OpenRouter API key is configured."""
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
        """Run one OpenRouter request and normalize the response."""
        import httpx

        image_urls = parts_to_image_urls(parts)
        content: list[dict[str, Any]] = [{"type": "text", "text": instruction}]
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            # Optional attribution headers recommended by OpenRouter.
            "HTTP-Referer": "https://indiaglycols.com",
            "X-Title": "India Glycols Document Intelligence",
        }

        try:
            with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
                response = client.post(_ENDPOINT, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise TransientAIError(f"OpenRouter request timed out: {exc}") from exc
        except httpx.TransportError as exc:  # connection/DNS/reset
            raise TransientAIError(f"OpenRouter connection error: {exc}") from exc

        if response.status_code >= 400:
            self._raise_for_status(response.status_code, response)

        try:
            data = response.json()
        except ValueError as exc:
            raise TransientAIError("OpenRouter returned a non-JSON response.") from exc

        # OpenRouter can return a 200 with an embedded error object.
        error = data.get("error")
        if error:
            code = _int_or_none(error.get("code"))
            message = str(error.get("message") or "OpenRouter error")
            if code in _TRANSIENT_STATUS:
                raise TransientAIError(message)
            raise FatalAIError(message)

        choices = data.get("choices") or []
        if not choices:
            raise TransientAIError("OpenRouter returned no choices.")
        text = ((choices[0] or {}).get("message") or {}).get("content") or ""
        if not text:
            raise TransientAIError("OpenRouter returned empty content.")

        return ProviderResponse(text=text, usage=_usage(data), model=model)

    @staticmethod
    def _raise_for_status(status: int, response: Any) -> None:
        """Translate an HTTP error status into a typed AI error (no key leakage)."""
        detail = _error_detail(response)
        message = f"OpenRouter HTTP {status}: {detail}" if detail else f"OpenRouter HTTP {status}"
        if status in _TRANSIENT_STATUS:
            raise TransientAIError(message)
        raise FatalAIError(message)


def _error_detail(response: Any) -> str:
    """Best-effort human-readable error text from an OpenRouter error response."""
    try:
        body = response.json()
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("message") or "")
        if isinstance(err, str):
            return err
    except Exception:  # noqa: BLE001 - body may not be JSON
        pass
    return ""


def _int_or_none(value: Any) -> int | None:
    """Coerce a value to int, or None when not numeric."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _usage(data: dict[str, Any]) -> dict[str, int]:
    """Map an OpenAI-style ``usage`` block to the platform's token shape."""
    usage = data.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens", 0) or 0)
    output_tokens = int(usage.get("completion_tokens", 0) or 0)
    total = int(usage.get("total_tokens", 0) or (input_tokens + output_tokens))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
    }
