"""
journal/logger.py — Dual-output logging for Signal Brain.

Provides get_logger(name) which returns a logger that writes to both
stdout and a rotating log file at logs/signal_brain.log.

Requires:
    config.LOG_FILE and config.LOG_LEVEL to be importable.

Returns:
    logging.Logger configured with console and rotating file handlers.
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def _ensure_log_dir(log_file: str) -> None:
    """Create the directory for log_file if it does not exist."""
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)


def _make_formatter() -> logging.Formatter:
    """Return the standard log line formatter."""
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger writing to both console and a rotating log file.

    Safe to call multiple times for the same name — handlers are not duplicated.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        Configured logging.Logger.
    """
    from config import LOG_FILE, LOG_LEVEL  # deferred to avoid circular import

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(level)
    formatter = _make_formatter()

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    _ensure_log_dir(LOG_FILE)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
