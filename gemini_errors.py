"""Shared Gemini error classification and rotation helper.

Detects rate-limit / quota / resource-exhausted failures in an SDK-version
tolerant way (by HTTP status and message markers, not a specific exception
class), and runs a request across all keys with transparent rotation.

Centralizing this keeps the rotation policy identical for every Gemini caller
(extraction client and document classifier).
"""

from __future__ import annotations

import logging
from typing import Callable, TypeVar

from api_key_manager import AllKeysExhausted, GeminiKeyManager

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Friendly message shown to users when every key is rate-limited.
ALL_KEYS_RATE_LIMITED_MESSAGE = (
    "All configured Gemini API keys have reached their rate limits. "
    "Please try again later."
)

_RATE_LIMIT_MARKERS = (
    "429",
    "too many requests",
    "resource_exhausted",
    "resource exhausted",
    "quota",
    "rate limit",
    "rate-limit",
    "ratelimit",
)


def is_rate_limit_error(exc: BaseException) -> bool:
    """Return True if an exception represents a rate-limit / quota failure.

    Args:
        exc: The exception raised by a Gemini SDK call.

    Returns:
        True for 429 / quota / resource-exhausted style errors.
    """
    # Prefer a structured status code when the SDK exposes one.
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 429:
        return True
    status = getattr(exc, "status", None)
    if isinstance(status, str) and "RESOURCE_EXHAUSTED" in status.upper():
        return True

    text = str(exc).lower()
    return any(marker in text for marker in _RATE_LIMIT_MARKERS)


def run_with_rotation(
    manager: GeminiKeyManager,
    call: Callable[[str], T],
) -> T:
    """Run ``call`` with the active key, rotating across keys on rate limits.

    The callable receives an API key value and performs a single Gemini request.
    On a rate-limit error, the active key is marked exhausted and the next
    available key is used — transparently, without re-uploading the document.

    Args:
        manager: The key manager providing keys and tracking health.
        call: A function that takes a key value and returns a result.

    Returns:
        The result of the first successful call.

    Raises:
        AllKeysExhausted: If every key is rate-limited (carrying the friendly
            message).
        Exception: Any non-rate-limit error is re-raised unchanged.
    """
    manager.require_keys()
    attempts = manager.total_keys

    for attempt in range(1, attempts + 1):
        key = manager.current_key()
        try:
            result = call(key)
            logger.info("Gemini request succeeded on Key #%d.", manager.active_number)
            return result
        except AllKeysExhausted:
            raise
        except Exception as exc:  # noqa: BLE001 - decide rotate vs re-raise
            if not is_rate_limit_error(exc):
                # Non-rate-limit failure: do not rotate; surface as-is.
                raise
            logger.warning(
                "Key #%d hit a rate limit on attempt %d/%d; rotating.",
                manager.active_number,
                attempt,
                attempts,
            )
            manager.mark_exhausted(reason="rate limit / quota")
            if not manager.has_available_key():
                break
            manager.rotate()

    raise AllKeysExhausted(ALL_KEYS_RATE_LIMITED_MESSAGE)
