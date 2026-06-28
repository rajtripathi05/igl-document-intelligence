"""Enterprise AI Gateway — the single entry point for every Gemini request.

Every AI request in the platform (Purchase Order, Shipping Bill, future
processors, and document classification) flows through one :class:`AIGateway`.
No processor talks to Gemini directly. The gateway maximizes uptime by
automatically failing over across both API keys and Gemini models before ever
reporting a failure to the user — who never needs to know which key or model
ultimately served the request.

Failover strategy (per request)
-------------------------------
A single *cycle* tries every configured model against every available key:

    for model in models:           # priority order
        for key in keys:           # rotation, immediate on failure
            try call(key, model) -> success, return immediately

Key rotation and model switching happen with **no sleep** — throughput and fast
recovery are the priority. Exponential backoff is applied **only between full
cycles**, once every model/key combination has failed once:

    cycle 1 fails -> sleep 1s
    cycle 2 fails -> sleep 2s
    cycle 3 fails -> sleep 4s   (capped at MAX_CYCLES)

After the maximum number of cycles the gateway raises
:class:`AIServiceUnavailable` carrying a clean, user-facing message.

Error handling
--------------
Retryable errors (HTTP 429/500/502/503/504, resource-exhausted, service
unavailable, deadline exceeded, timeouts, connection errors) trigger failover.
Fatal errors (invalid key, invalid request, unsupported model, prompt/safety
violations) surface immediately — see :mod:`gemini_errors`.

Security & logging
------------------
API key values are never logged, displayed, saved, or placed in exceptions; keys
are referenced only by their 1-based number (e.g. "Key #2"). Each rotation,
retry, model switch, and final success is logged for observability.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar

from api_key_manager import GeminiKeyManager, NoApiKeysConfigured
from gemini_errors import AI_SERVICE_UNAVAILABLE_MESSAGE, is_fatal_error

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Environment variable prefix for numbered models (e.g. GEMINI_MODEL_1).
_NUMBERED_MODEL_PREFIX = "GEMINI_MODEL_"
#: Bare single-model variable name (backward compatibility).
_BARE_MODEL_NAME = "GEMINI_MODEL"
_NUMBERED_MODEL_RE = re.compile(r"^GEMINI_MODEL_(\d+)$")
#: Final fallback model when nothing is configured.
_DEFAULT_MODEL = "gemini-2.5-flash"

#: Maximum number of full failover cycles before giving up.
MAX_CYCLES = 3
#: Per-cycle backoff seconds (index = completed cycle count). Applied only
#: between cycles, never between key or model rotations.
_BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0)


class AIServiceUnavailable(RuntimeError):
    """Raised when every model and key has been exhausted across all cycles."""

    def __init__(self, message: str = AI_SERVICE_UNAVAILABLE_MESSAGE) -> None:
        super().__init__(message)


def discover_models() -> list[str]:
    """Discover the configured Gemini models in priority order.

    Discovery order:
        1. ``GEMINI_MODEL_<n>`` variables, sorted numerically (highest priority
           first: ``GEMINI_MODEL_1`` is tried before ``GEMINI_MODEL_2``).
        2. The bare ``GEMINI_MODEL`` (backward compatibility), appended if set
           and not already present.
        3. A single built-in default if nothing is configured.

    Duplicates are removed while preserving first-seen priority order. Models are
    never hardcoded inside the extraction engine — only here.

    Returns:
        A non-empty list of model identifiers in priority order.
    """
    numbered: list[tuple[int, str]] = []
    for name, value in os.environ.items():
        match = _NUMBERED_MODEL_RE.match(name)
        if match and value and value.strip():
            numbered.append((int(match.group(1)), value.strip()))
    numbered.sort(key=lambda item: item[0])

    ordered: list[str] = []
    for _, value in numbered:
        if value not in ordered:
            ordered.append(value)

    bare = os.getenv(_BARE_MODEL_NAME)
    if bare and bare.strip() and bare.strip() not in ordered:
        ordered.append(bare.strip())

    if not ordered:
        ordered.append(_DEFAULT_MODEL)

    return ordered


@dataclass
class GatewayStatus:
    """A non-sensitive snapshot of the gateway's most recent activity.

    Safe for display in the development UI. Contains no key values.

    Attributes:
        model: The model used on the last attempt.
        key_number: 1-based number of the key used on the last attempt.
        total_keys: Total configured keys.
        retries: Failover attempts made on the most recent request (0 on a clean
            first-try success).
        cycle: The cycle index reached on the most recent request (1-based).
        healthy: True if the most recent request ultimately succeeded.
    """

    model: str = ""
    key_number: int = 0
    total_keys: int = 0
    retries: int = 0
    cycle: int = 1
    healthy: bool = True

    def as_dict(self) -> dict[str, object]:
        """Return a plain-dict view for the UI layer."""
        return {
            "model": self.model,
            "key_number": self.key_number,
            "total_keys": self.total_keys,
            "retries": self.retries,
            "cycle": self.cycle,
            "healthy": self.healthy,
        }


class AIGateway:
    """Single entry point that runs an AI request with key + model failover.

    The gateway owns the failover policy. Callers supply a model-agnostic,
    key-agnostic callable; the gateway decides which model and key to use and
    retries transparently on transient failures.
    """

    def __init__(
        self,
        key_manager: GeminiKeyManager,
        models: list[str] | None = None,
    ) -> None:
        """Initialize the gateway.

        Args:
            key_manager: The shared Gemini key manager (sole source of keys).
            models: Optional explicit model priority list (mainly for testing).
                When omitted, models are discovered from the environment.
        """
        self._keys = key_manager
        self._models = models if models is not None else discover_models()
        self._lock = threading.Lock()
        self._status = GatewayStatus(
            model=self._models[0],
            total_keys=key_manager.total_keys,
            healthy=key_manager.has_keys(),
        )
        logger.info(
            "AI Gateway initialized with %d model(s) %s and %d key(s).",
            len(self._models),
            self._models,
            key_manager.total_keys,
        )

    # ----- Availability -------------------------------------------------- #

    @property
    def models(self) -> list[str]:
        """Configured models in priority order (defensive copy)."""
        return list(self._models)

    def has_capacity(self) -> bool:
        """True if at least one key is configured (a request can be attempted)."""
        return self._keys.has_keys()

    def status(self) -> dict[str, object]:
        """Return a non-sensitive status snapshot for the development UI."""
        with self._lock:
            return self._status.as_dict()

    def _record(self, status: GatewayStatus) -> None:
        """Atomically store the latest status snapshot."""
        with self._lock:
            self._status = status

    # ----- Core entry point ---------------------------------------------- #

    def generate(self, call: Callable[[str, str], T]) -> T:
        """Run an AI request with full key + model failover.

        The ``call`` receives ``(api_key, model)`` and performs exactly one
        Gemini request, returning its result. The gateway selects the model and
        key and retries transparently across all of them on transient errors.

        Args:
            call: A callable taking ``(api_key, model)`` and returning a result.

        Returns:
            The result of the first successful call.

        Raises:
            NoApiKeysConfigured: If no API keys are configured at all.
            AIServiceUnavailable: If every model/key fails across all cycles.
            Exception: Any *fatal* (non-retryable) error is re-raised unchanged.
        """
        self._keys.require_keys()
        total_keys = self._keys.total_keys
        retries = 0
        last_retryable_exc: BaseException | None = None

        for cycle in range(1, MAX_CYCLES + 1):
            for model in self._models:
                # A model attempt gets a fresh look at every key, so clear any
                # key-exhaustion flags set earlier in this request.
                self._keys.reset_health()
                for _ in range(total_keys):
                    key_number = self._keys.active_number
                    logger.info(
                        "Gateway attempt — Model %s, Key #%d, Cycle %d.",
                        model,
                        key_number,
                        cycle,
                    )
                    try:
                        key = self._keys.current_key()
                        result = call(key, model)
                    except NoApiKeysConfigured:
                        raise
                    except Exception as exc:  # noqa: BLE001 - classify & decide
                        if is_fatal_error(exc):
                            logger.error(
                                "Fatal Gemini error on Model %s, Key #%d; "
                                "not retrying.",
                                model,
                                key_number,
                            )
                            self._record(
                                GatewayStatus(
                                    model=model,
                                    key_number=key_number,
                                    total_keys=total_keys,
                                    retries=retries,
                                    cycle=cycle,
                                    healthy=False,
                                )
                            )
                            raise
                        last_retryable_exc = exc
                        retries += 1
                        logger.warning(
                            "Retryable error on Model %s, Key #%d (retry %d): %s",
                            model,
                            key_number,
                            retries,
                            exc,
                        )
                        self._keys.mark_exhausted(reason="retryable error")
                        if self._keys.has_available_key():
                            # Immediate key rotation — no sleep.
                            self._keys.rotate()
                            continue
                        # No keys left for this model; move to the next model.
                        logger.info(
                            "All keys failed for Model %s; switching model.", model
                        )
                        break
                    else:
                        self._record(
                            GatewayStatus(
                                model=model,
                                key_number=key_number,
                                total_keys=total_keys,
                                retries=retries,
                                cycle=cycle,
                                healthy=True,
                            )
                        )
                        logger.info(
                            "Request successful on Model %s, Key #%d "
                            "after %d retr%s.",
                            model,
                            key_number,
                            retries,
                            "y" if retries == 1 else "ies",
                        )
                        return result

            # Every model/key failed this cycle. Back off before the next cycle,
            # but never after the final cycle.
            if cycle < MAX_CYCLES:
                delay = _BACKOFF_SECONDS[min(cycle - 1, len(_BACKOFF_SECONDS) - 1)]
                logger.warning(
                    "Cycle %d exhausted all models/keys; backing off %.0fs "
                    "before cycle %d.",
                    cycle,
                    delay,
                    cycle + 1,
                )
                time.sleep(delay)

        self._record(
            GatewayStatus(
                model=self._models[0],
                key_number=self._keys.active_number,
                total_keys=total_keys,
                retries=retries,
                cycle=MAX_CYCLES,
                healthy=False,
            )
        )
        logger.error(
            "AI Gateway exhausted all models/keys across %d cycle(s).", MAX_CYCLES
        )
        raise AIServiceUnavailable() from last_retryable_exc
