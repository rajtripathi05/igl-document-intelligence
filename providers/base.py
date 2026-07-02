"""The provider-neutral AI contract.

A :class:`Provider` receives a fully-built, provider-agnostic request (system
prompt, instruction text, and a list of document ``(bytes, mime_type)`` parts)
and returns a normalized :class:`ProviderResponse` (text + token usage). It is
the ONLY place that knows how to talk to a specific AI backend.

Providers classify their own failures into exactly two categories so the gateway
can apply a single, uniform retry policy:

- :class:`TransientAIError` — rate limits, server errors, timeouts, connection
  problems. The gateway retries (and may escalate to the RETRY model).
- :class:`FatalAIError` — invalid key, invalid request, unsupported model,
  prompt/safety violations. Retrying cannot help; the gateway surfaces it.

Security: an API key value is never logged, displayed, saved, or placed in an
exception message by any provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class AIError(RuntimeError):
    """Base class for every provider-raised AI failure."""


class TransientAIError(AIError):
    """A transient failure worth retrying (rate limit, 5xx, timeout, network)."""


class FatalAIError(AIError):
    """A permanent failure that retrying cannot fix (bad key/request/model)."""


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized result of a single provider call.

    Attributes:
        text: The raw model text output (expected to be JSON for extraction).
        usage: ``{"input_tokens", "output_tokens", "total_tokens"}`` (best-effort;
            zeros when the backend does not report usage).
        model: The concrete model id that served the request.
    """

    text: str
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


class Provider(ABC):
    """A single AI backend behind the provider-agnostic gateway."""

    #: Short, stable provider identifier (e.g. ``"openrouter"``, ``"gemini"``).
    name: str = "provider"

    @property
    @abstractmethod
    def has_key(self) -> bool:
        """True if this provider was configured with an API key."""

    @abstractmethod
    def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        instruction: str,
        parts: list[tuple[bytes, str]],
        json_mode: bool = True,
    ) -> ProviderResponse:
        """Run one AI request and return a normalized response.

        Args:
            model: The concrete model id to use.
            system_prompt: System instruction (may be empty).
            instruction: The user instruction / task text.
            parts: Document parts as ``(bytes, mime_type)`` (PDF and/or images).
            json_mode: Request a JSON object response when the backend supports it.

        Returns:
            A :class:`ProviderResponse`.

        Raises:
            TransientAIError: On a retryable failure.
            FatalAIError: On a permanent failure.
        """
