"""Provider-agnostic AI backend package.

The platform talks to AI models exclusively through a small, uniform
:class:`~providers.base.Provider` contract. Concrete providers (OpenRouter,
Google Gemini, and any future Claude/OpenAI/DeepSeek/Qwen backend) translate the
provider-neutral request into their own SDK/REST call and normalize the response.

Processors and the extraction engine never import a concrete provider — they call
the shared :class:`AIGateway`, which owns the selected provider and the
DEFAULT/RETRY model policy. Switching provider or models is a ``.env`` change only.
"""

from __future__ import annotations

from providers.base import (
    AIError,
    FatalAIError,
    Provider,
    ProviderResponse,
    TransientAIError,
)
from providers.factory import build_provider

__all__ = [
    "AIError",
    "FatalAIError",
    "Provider",
    "ProviderResponse",
    "TransientAIError",
    "build_provider",
]
