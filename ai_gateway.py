"""Enterprise AI Gateway — the single, provider-agnostic entry point for AI.

Every AI request in the platform (Sales Order, Shipping Bill, IGP, future
processors, and document classification) flows through one :class:`AIGateway`.
No processor talks to a provider directly, and no processor knows which provider
or model is used — that is chosen entirely from ``.env`` (see :mod:`providers`).

Model policy
------------
- **DEFAULT_MODEL** serves normal processing.
- **RETRY_MODEL** serves the single, user-triggered retry (a stronger model).

Resilience
----------
Within one call the gateway retries *transient* provider errors (rate limits,
5xx, timeouts, connection problems) with exponential backoff on the single
configured key. *Fatal* errors (bad key/request/model, prompt/safety) surface
immediately. When transient retries are exhausted the gateway raises
:class:`AIServiceUnavailable` with a clean, user-facing message.

Security & logging
------------------
API key values are never logged, displayed, saved, or placed in exceptions. Each
attempt, retry, model, and final outcome is logged for observability.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from gemini_errors import AI_SERVICE_UNAVAILABLE_MESSAGE
from providers.base import (
    AIError,
    FatalAIError,
    Provider,
    ProviderResponse,
    TransientAIError,
)

logger = logging.getLogger(__name__)

#: Maximum attempts for a single model call (1 initial + retries).
MAX_ATTEMPTS = 3
#: Backoff seconds between attempts (index = completed attempt count).
_BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0)


class AIServiceUnavailable(RuntimeError):
    """Raised when transient retries are exhausted, or no provider key is set."""

    def __init__(self, message: str = AI_SERVICE_UNAVAILABLE_MESSAGE) -> None:
        super().__init__(message)


@dataclass
class GatewayStatus:
    """A non-sensitive snapshot of the gateway's most recent activity.

    Safe for display in the enterprise UI. Contains no key values.
    """

    provider: str = ""
    model: str = ""
    default_model: str = ""
    retry_model: str = ""
    retries: int = 0
    used_retry_model: bool = False
    healthy: bool = True

    def as_dict(self) -> dict[str, object]:
        """Return a plain-dict view for the UI layer (backward-compatible keys)."""
        return {
            "provider": self.provider,
            "model": self.model,
            "default_model": self.default_model,
            "retry_model": self.retry_model,
            "retries": self.retries,
            "used_retry_model": self.used_retry_model,
            "healthy": self.healthy,
            # Legacy keys retained so older UI code keeps working.
            "key_number": 1 if self.healthy else 0,
            "total_keys": 1,
            "cycle": 1,
        }


class AIGateway:
    """Provider + model orchestrator — the sole entry point for AI requests."""

    def __init__(
        self,
        provider: Provider | None,
        default_model: str,
        retry_model: str,
    ) -> None:
        """Initialize the gateway.

        Args:
            provider: The configured AI provider (from :func:`providers.build_provider`).
            default_model: Model used for normal processing.
            retry_model: Stronger model used for the single user-triggered retry.
        """
        self._provider = provider
        self._default_model = default_model
        self._retry_model = retry_model
        self._lock = threading.Lock()
        self._stage = "Idle"
        self._queue = 0
        self._status = GatewayStatus(
            provider=provider.name if provider else "none",
            model=default_model,
            default_model=default_model,
            retry_model=retry_model,
            healthy=bool(provider and provider.has_key),
        )
        logger.info(
            "AI Gateway initialized (provider=%s, default=%s, retry=%s, key=%s).",
            provider.name if provider else "none",
            default_model,
            retry_model,
            "present" if (provider and provider.has_key) else "MISSING",
        )

    # ----- Configuration / availability --------------------------------- #

    @property
    def provider_name(self) -> str:
        """Name of the active provider (never a key)."""
        return self._provider.name if self._provider else "none"

    @property
    def default_model(self) -> str:
        """The DEFAULT_MODEL id."""
        return self._default_model

    @property
    def retry_model(self) -> str:
        """The RETRY_MODEL id."""
        return self._retry_model

    def model_for(self, use_retry_model: bool) -> str:
        """Return the model id for a normal (False) or retry (True) request."""
        return self._retry_model if use_retry_model else self._default_model

    def has_capacity(self) -> bool:
        """True if a provider with an API key is configured (a call can run)."""
        return bool(self._provider and self._provider.has_key)

    def status(self) -> dict[str, object]:
        """Return a non-sensitive status snapshot (merged with live stage/queue)."""
        with self._lock:
            snapshot = self._status.as_dict()
            snapshot["stage"] = self._stage
            snapshot["queue"] = self._queue
            return snapshot

    def set_stage(self, stage: str) -> None:
        """Record the current human-readable processing stage (for the UI)."""
        with self._lock:
            self._stage = stage

    def set_queue(self, queue: int) -> None:
        """Record the number of documents waiting in the processing queue."""
        with self._lock:
            self._queue = max(0, int(queue))

    def _record(self, status: GatewayStatus) -> None:
        """Atomically store the latest status snapshot."""
        with self._lock:
            self._status = status

    # ----- Core entry point ---------------------------------------------- #

    def extract(
        self,
        *,
        system_prompt: str,
        instruction: str,
        parts: list[tuple[bytes, str]],
        json_mode: bool = True,
        use_retry_model: bool = False,
    ) -> ProviderResponse:
        """Run one AI request with transient-error backoff on the single key.

        Args:
            system_prompt: System instruction (may be empty).
            instruction: The task/extraction instruction text.
            parts: Document parts as ``(bytes, mime_type)``.
            json_mode: Request a JSON object response when supported.
            use_retry_model: When True, use RETRY_MODEL instead of DEFAULT_MODEL.

        Returns:
            The provider's normalized :class:`ProviderResponse`.

        Raises:
            AIServiceUnavailable: If no key is configured or transient retries fail.
            FatalAIError: On a permanent provider error (bad key/request/model).
        """
        if not self.has_capacity():
            self._record(
                GatewayStatus(
                    provider=self.provider_name,
                    model=self.model_for(use_retry_model),
                    default_model=self._default_model,
                    retry_model=self._retry_model,
                    used_retry_model=use_retry_model,
                    healthy=False,
                )
            )
            raise AIServiceUnavailable()

        assert self._provider is not None  # guarded by has_capacity()
        model = self.model_for(use_retry_model)
        retries = 0
        last_exc: BaseException | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            logger.info(
                "Gateway attempt %d/%d — provider=%s, model=%s%s.",
                attempt,
                MAX_ATTEMPTS,
                self.provider_name,
                model,
                " (RETRY_MODEL)" if use_retry_model else "",
            )
            try:
                result = self._provider.generate(
                    model=model,
                    system_prompt=system_prompt,
                    instruction=instruction,
                    parts=parts,
                    json_mode=json_mode,
                )
            except FatalAIError:
                self._record(
                    GatewayStatus(
                        provider=self.provider_name,
                        model=model,
                        default_model=self._default_model,
                        retry_model=self._retry_model,
                        retries=retries,
                        used_retry_model=use_retry_model,
                        healthy=False,
                    )
                )
                logger.error("Fatal provider error on model %s; not retrying.", model)
                raise
            except (TransientAIError, AIError) as exc:
                last_exc = exc
                retries += 1
                logger.warning(
                    "Transient error on model %s (attempt %d): %s",
                    model,
                    attempt,
                    exc,
                )
                if attempt < MAX_ATTEMPTS:
                    delay = _BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)]
                    time.sleep(delay)
                    continue
                break
            else:
                self._record(
                    GatewayStatus(
                        provider=self.provider_name,
                        model=model,
                        default_model=self._default_model,
                        retry_model=self._retry_model,
                        retries=retries,
                        used_retry_model=use_retry_model,
                        healthy=True,
                    )
                )
                logger.info(
                    "Request successful on model %s after %d retr%s.",
                    model,
                    retries,
                    "y" if retries == 1 else "ies",
                )
                return result

        self._record(
            GatewayStatus(
                provider=self.provider_name,
                model=model,
                default_model=self._default_model,
                retry_model=self._retry_model,
                retries=retries,
                used_retry_model=use_retry_model,
                healthy=False,
            )
        )
        logger.error("AI Gateway exhausted %d attempt(s) on model %s.", MAX_ATTEMPTS, model)
        raise AIServiceUnavailable() from last_exc
