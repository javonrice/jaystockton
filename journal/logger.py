"""
journal/logger.py — Dual-output logging and signal storage for Signal Brain.

Provides get_logger(name) for dual console+file logging, and
init_signals_table / store_signal for DuckDB signal journaling.

Requires:
    config.LOG_FILE and config.LOG_LEVEL to be importable.

Returns:
    get_logger, init_signals_table, store_signal.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any

import duckdb


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


def init_signals_table(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Create the signals table if it does not exist.

    Schema: ticker, date, signal_type, direction, close, volume,
            avg_volume, volume_ratio, high_20d, created_at.
    PRIMARY KEY on (ticker, date, signal_type) prevents duplicate signals.

    Args:
        conn: Open DuckDB connection.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            ticker       TEXT        NOT NULL,
            date         DATE        NOT NULL,
            signal_type  TEXT        NOT NULL,
            direction    TEXT        NOT NULL,
            close        DOUBLE      NOT NULL,
            volume       BIGINT      NOT NULL,
            avg_volume   DOUBLE      NOT NULL,
            volume_ratio DOUBLE      NOT NULL,
            high_20d     DOUBLE      NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ticker, date, signal_type)
        )
    """)


def store_signal(conn: duckdb.DuckDBPyConnection, signal: dict[str, Any]) -> None:
    """
    Persist one signal dict to the signals table.

    Skips silently if the same (ticker, date, signal_type) already exists.

    Args:
        conn: Open DuckDB connection with signals table initialised.
        signal: Dict with keys matching the signals schema.
    """
    conn.execute(
        """
        INSERT INTO signals
            (ticker, date, signal_type, direction, close, volume,
             avg_volume, volume_ratio, high_20d, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (ticker, date, signal_type) DO NOTHING
        """,
        [
            signal["ticker"], signal["date"], signal["signal_type"],
            signal["direction"], signal["close"], signal["volume"],
            signal["avg_volume"], signal["volume_ratio"], signal["high_20d"],
        ],
    )
