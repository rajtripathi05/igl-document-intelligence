"""Gemini error classification for the Enterprise AI Gateway.

Classifies failures from the Google Gemini SDK in an SDK-version-tolerant way
(by HTTP status code and message markers, not a specific exception class) so the
gateway can decide whether to fail over to the next key/model or surface the
error immediately.

Two categories:

- **Retryable** — transient infrastructure failures (rate limits, server errors,
  timeouts, connection problems). The gateway rotates keys/models and retries.
- **Fatal** — caller/configuration errors (invalid key, invalid request,
  unsupported model, prompt/safety violations). Retrying cannot help, so these
  surface immediately without burning the rotation budget.

When a failure matches neither list it is treated as retryable: maximizing
uptime is the priority, and an unknown transient is more likely than an unknown
permanent fault.

Security: no API key value is ever read, logged, or placed in an exception here.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Friendly message surfaced to users once every key and model is exhausted.
AI_SERVICE_UNAVAILABLE_MESSAGE = "AI Service Temporarily Unavailable"

#: HTTP status codes that should trigger key/model failover.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

#: HTTP status codes that are permanent for this request (never retry).
_FATAL_STATUS_CODES = frozenset({400, 401, 403, 404, 422})

#: Lower-cased message markers indicating a transient, retryable failure.
_RETRYABLE_MARKERS = (
    "429",
    "500",
    "502",
    "503",
    "504",
    "too many requests",
    "resource_exhausted",
    "resource exhausted",
    "quota",
    "rate limit",
    "rate-limit",
    "ratelimit",
    "unavailable",
    "service unavailable",
    "deadline",
    "deadline_exceeded",
    "deadline exceeded",
    "timeout",
    "timed out",
    "connection",
    "connection error",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
    "internal error",
    "internal server error",
    "overloaded",
    "try again",
)

#: Lower-cased message markers indicating a permanent, fatal failure. These take
#: precedence over retryable markers so e.g. "invalid api key" never rotates.
_FATAL_MARKERS = (
    "api key not valid",
    "api_key_invalid",
    "invalid api key",
    "invalid_api_key",
    "permission denied",
    "permission_denied",
    "unauthenticated",
    "invalid argument",
    "invalid_argument",
    "invalid request",
    "failed_precondition",
    "not found",
    "not_found",
    "is not found",
    "is not supported",
    "unsupported",
    "unknown model",
    "prompt",
    "safety",
    "blocked",
    "recitation",
)


def _status_code(exc: BaseException) -> int | None:
    """Best-effort extraction of an HTTP status code from an SDK exception."""
    for attr in ("code", "status_code", "http_status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def is_fatal_error(exc: BaseException) -> bool:
    """Return True if an exception is permanent and must not be retried.

    Fatal errors (invalid key, invalid request, unsupported model, prompt/safety
    failures) cannot be fixed by rotating to another key or model, so the gateway
    surfaces them immediately rather than wasting the rotation budget.

    Args:
        exc: The exception raised by a Gemini SDK call.

    Returns:
        True for permanent caller/configuration errors.
    """
    code = _status_code(exc)
    if code in _FATAL_STATUS_CODES:
        return True
    if code in _RETRYABLE_STATUS_CODES:
        return False
    text = str(exc).lower()
    return any(marker in text for marker in _FATAL_MARKERS)


def is_retryable_error(exc: BaseException) -> bool:
    """Return True if an exception is transient and worth a key/model failover.

    Covers HTTP 429/500/502/503/504, resource-exhausted / service-unavailable /
    deadline-exceeded statuses, and timeout / connection failures. Fatal errors
    are excluded first. Unknown failures default to retryable to favour uptime.

    Args:
        exc: The exception raised by a Gemini SDK call.

    Returns:
        True if the gateway should rotate keys/models and retry.
    """
    if is_fatal_error(exc):
        return False

    code = _status_code(exc)
    if code in _RETRYABLE_STATUS_CODES:
        return True

    status = getattr(exc, "status", None)
    if isinstance(status, str):
        upper = status.upper()
        if any(
            marker in upper
            for marker in ("RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE_EXCEEDED")
        ):
            return True

    text = str(exc).lower()
    if any(marker in text for marker in _RETRYABLE_MARKERS):
        return True

    # Unknown failure: treat as transient to maximize uptime.
    logger.debug("Unclassified Gemini error treated as retryable: %s", exc)
    return True
