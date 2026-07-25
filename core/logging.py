"""
Centralized logging for ComfyUI-LK-Model_Auto-Matching.

Provides a drop-in logger that routes through Python's logging framework
while maintaining backward-compatible output to ComfyUI's console.

Usage:
    from .logging import get_logger
    logger = get_logger(__name__)
    logger.info("Scanning models...")
    logger.warning("Circuit breaker open for %s", provider_name)
    logger.debug("Hash cache hit: %s", file_path)
"""

import logging
import sys

_FORMATTER = logging.Formatter(
    "[%(name)s] %(levelname)s: %(message)s"
)

# Module-level cache so each module gets its own logger
_loggers: dict[str, logging.Logger] = {}

# Root logger for the plugin — controls global verbosity
_ROOT = logging.getLogger("AutoModelMatcher")
_ROOT.setLevel(logging.INFO)

# Default handler writes to stdout (ComfyUI captures this)
if not _ROOT.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(_FORMATTER)
    _ROOT.addHandler(_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger of the plugin root.

    The *name* should be ``__name__`` from the calling module for proper
    hierarchical naming (e.g. ``AutoModelMatcher.core.scanner``).
    """
    if name not in _loggers:
        # Normalize: strip leading dots so "core.scanner" maps cleanly
        clean = name.removeprefix(".")
        _loggers[name] = _ROOT.getChild(clean)
    return _loggers[name]


def set_level(level: int | str) -> None:
    """Set the global log level for the plugin (DEBUG / INFO / WARNING / ERROR)."""
    _ROOT.setLevel(level)


def enable_debug() -> None:
    """Convenience: enable debug-level logging."""
    _ROOT.setLevel(logging.DEBUG)
