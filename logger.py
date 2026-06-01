"""
logger.py — Structured logging for the trading bot.

* Console handler  → INFO and above (human-readable, coloured)
* File handler     → DEBUG and above (full detail, timestamped)
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config import LOG_FILE, LOG_LEVEL

_COLOURS = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[35m",   # magenta
}
_RESET = "\033[0m"


class _ColouredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        colour = _COLOURS.get(record.levelname, "")
        record.levelname = f"{colour}{record.levelname:<8}{_RESET}"
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """Return (or create) a named logger attached to the shared handlers."""
    root = logging.getLogger("trading_bot")

    if not root.handlers:
        root.setLevel(logging.DEBUG)

        # ── File handler (full detail) ──────────────────────────────────
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,   # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

        # ── Console handler (INFO+, coloured) ──────────────────────────
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            _ColouredFormatter(
                fmt="%(asctime)s %(levelname)s %(message)s",
                datefmt="%H:%M:%S",
            )
        )

        root.addHandler(file_handler)
        root.addHandler(console_handler)

    return root.getChild(name)
