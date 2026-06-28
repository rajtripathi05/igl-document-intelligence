"""Gemini API key manager.

Centralizes discovery, rotation, and health tracking of Google Gemini API keys
so that no other part of the application reads key environment variables
directly. All Gemini requests obtain keys exclusively through this manager.

Key discovery:
    - Any environment variable named ``GEMINI_API_KEY_<n>`` (numerically sorted).
    - The bare ``GEMINI_API_KEY`` (backward compatibility) is appended if present
      and not already covered.

Rotation & health:
    - Keys are handed out one at a time; the active index is tracked.
    - A key can be marked *exhausted* (quota/rate-limit) for the session; the
      manager skips it for the rest of the session.
    - When every key is exhausted the manager reports it so the caller can show
      a friendly message.

Security:
    - Actual key values are never logged, displayed, saved, or placed in
      exceptions. Keys are referenced only by their 1-based number (e.g. "#2").

Future-ready:
    - This is the single seam for authentication. Replacing multiple development
      keys with one production key, Vertex AI, or a service account means
      providing an alternative manager with the same public surface — no other
      module changes.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

#: Environment variable prefix for numbered keys (e.g. GEMINI_API_KEY_1).
_NUMBERED_PREFIX = "GEMINI_API_KEY_"
#: Bare single-key variable name (backward compatibility).
_BARE_NAME = "GEMINI_API_KEY"
_NUMBERED_RE = re.compile(r"^GEMINI_API_KEY_(\d+)$")


class NoApiKeysConfigured(RuntimeError):
    """Raised when no Gemini API keys are configured in the environment."""


class AllKeysExhausted(RuntimeError):
    """Raised when every configured key has been marked unavailable."""


@dataclass
class _KeyEntry:
    """Internal record for a single discovered key.

    Attributes:
        number: 1-based display number used in logs and the UI.
        value: The secret key value (never logged or displayed).
        exhausted: True once the key hits quota/rate-limit this session.
    """

    number: int
    value: str
    exhausted: bool = False


def _discover_keys() -> list[str]:
    """Discover all configured Gemini API key values from the environment.

    Returns:
        Key values in a stable order: numbered keys sorted numerically, then the
        bare ``GEMINI_API_KEY`` if present and not already included.
    """
    numbered: list[tuple[int, str]] = []
    for name, value in os.environ.items():
        match = _NUMBERED_RE.match(name)
        if match and value and value.strip():
            numbered.append((int(match.group(1)), value.strip()))
    numbered.sort(key=lambda item: item[0])

    values = [value for _, value in numbered]

    bare = os.getenv(_BARE_NAME)
    if bare and bare.strip() and bare.strip() not in values:
        values.append(bare.strip())

    return values


class GeminiKeyManager:
    """Manages the pool of Gemini API keys, rotation, and health tracking."""

    def __init__(self, keys: list[str] | None = None) -> None:
        """Initialize the manager.

        Args:
            keys: Optional explicit key values (mainly for testing). When omitted,
                keys are discovered from the environment.
        """
        discovered = keys if keys is not None else _discover_keys()
        self._entries: list[_KeyEntry] = [
            _KeyEntry(number=i + 1, value=v) for i, v in enumerate(discovered)
        ]
        self._active_index: int = 0
        if self._entries:
            logger.info(
                "Gemini key manager initialized with %d key(s).", len(self._entries)
            )
        else:
            logger.warning("Gemini key manager initialized with no keys.")

    # ----- Availability -------------------------------------------------- #

    @property
    def total_keys(self) -> int:
        """Total number of configured keys."""
        return len(self._entries)

    @property
    def available_count(self) -> int:
        """Number of keys not yet marked exhausted."""
        return sum(1 for e in self._entries if not e.exhausted)

    def has_keys(self) -> bool:
        """True if at least one key is configured."""
        return bool(self._entries)

    def has_available_key(self) -> bool:
        """True if at least one non-exhausted key remains."""
        return self.available_count > 0

    def require_keys(self) -> None:
        """Validate that at least one key is configured.

        Raises:
            NoApiKeysConfigured: If no keys were discovered.
        """
        if not self._entries:
            raise NoApiKeysConfigured(
                "No Gemini API keys configured. Set GEMINI_API_KEY or "
                "GEMINI_API_KEY_1, GEMINI_API_KEY_2, ... in the .env file."
            )

    # ----- Active key access --------------------------------------------- #

    @property
    def active_number(self) -> int:
        """1-based number of the currently active key (0 if none)."""
        if not self._entries:
            return 0
        return self._entries[self._active_index].number

    def current_key(self) -> str:
        """Return the active key value, advancing past exhausted keys.

        Returns:
            The active (non-exhausted) key value.

        Raises:
            NoApiKeysConfigured: If no keys are configured.
            AllKeysExhausted: If every key is exhausted.
        """
        self.require_keys()
        entry = self._entries[self._active_index]
        if entry.exhausted:
            entry = self._advance_to_available()
        logger.info("Using Gemini Key #%d.", entry.number)
        return entry.value

    def rotate(self) -> str:
        """Rotate to the next available key and return its value.

        Returns:
            The next available key value.

        Raises:
            AllKeysExhausted: If no available key remains.
        """
        current_number = self.active_number
        entry = self._advance_to_available()
        logger.info(
            "Rotating to Gemini Key #%d (from #%d).", entry.number, current_number
        )
        return entry.value

    def mark_exhausted(self, *, reason: str = "quota/rate-limit") -> None:
        """Mark the active key as exhausted for the rest of the session.

        Args:
            reason: Short, non-sensitive reason recorded in the log.
        """
        if not self._entries:
            return
        entry = self._entries[self._active_index]
        entry.exhausted = True
        logger.warning("Key #%d exhausted (%s).", entry.number, reason)

    def reset_health(self) -> None:
        """Clear all exhausted flags and rewind to the first key.

        Used to begin a fresh attempt cycle (e.g. when the gateway switches to a
        new model): every key becomes available again and rotation restarts from
        Key #1 so failover order is deterministic.
        """
        for entry in self._entries:
            entry.exhausted = False
        self._active_index = 0
        logger.info("Gemini key health reset; all keys available, rewound to #1.")

    # ----- Status (safe for UI) ------------------------------------------ #

    def status(self) -> dict[str, object]:
        """Return a non-sensitive status snapshot for display.

        Returns:
            A dict with ``active_number``, ``total``, ``available``, and a
            ``healthy`` flag. Contains no key values.
        """
        return {
            "active_number": self.active_number,
            "total": self.total_keys,
            "available": self.available_count,
            "healthy": self.has_available_key(),
        }

    # ----- Internals ----------------------------------------------------- #

    def _advance_to_available(self) -> _KeyEntry:
        """Advance the active index to the next non-exhausted key.

        Returns:
            The newly active key entry.

        Raises:
            AllKeysExhausted: If no available key remains.
        """
        total = len(self._entries)
        for step in range(1, total + 1):
            candidate = (self._active_index + step) % total
            if not self._entries[candidate].exhausted:
                self._active_index = candidate
                return self._entries[candidate]
        raise AllKeysExhausted(
            "All configured Gemini API keys have reached their rate limits."
        )
