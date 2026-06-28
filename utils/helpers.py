"""General helper utilities shared across the application."""

from __future__ import annotations

import logging
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once for the application.

    Args:
        level: Logging level to apply to the root logger.
    """
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(level=level, format=_LOG_FORMAT)


def read_text_file(path: Path) -> str:
    """Read a UTF-8 text file and return its contents.

    Args:
        path: Path to the text file.

    Returns:
        File contents as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    with path.open("r", encoding="utf-8") as handle:
        return handle.read()


def format_currency(value: object, currency: str = "") -> str:
    """Format a numeric value for display, tolerating missing values.

    Args:
        value: A number (or value coercible to float).
        currency: Optional currency code prefix.

    Returns:
        A formatted string, or an empty placeholder when not numeric.
    """
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "—"
    prefix = f"{currency} " if currency else ""
    return f"{prefix}{number:,.2f}"
