"""
signals/breakout.py — Layer 1+2: 20-day closing high breakout with volume confirmation.

Detects when a ticker's daily close exceeds its 20-day highest close AND
volume is at least 1.5x the 20-day average volume. Both conditions must
fire simultaneously for a signal to be returned.

Requires:
    daily_bars table populated via feeds.market_data.store_daily_bars.

Returns:
    detect_breakout: Optional signal dict for one ticker.
    scan_all_breakouts: List of signal dicts across all tickers.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

import duckdb

import config
from journal.logger import get_logger

logger = get_logger(__name__)


def detect_breakout(ticker: str, conn: duckdb.DuckDBPyConnection) -> Optional[dict[str, Any]]:
    """
    Return a signal dict if today's close is a 20-day high with 1.5x+ volume.

    Lookback window: the 20 most recent completed bars before today.
    Requires at least 21 rows (today + 20-day window). Returns None if
    either condition fails or data is insufficient.

    Args:
        ticker: Stock symbol to evaluate.
        conn: DuckDB connection with daily_bars table populated.

    Returns:
        Signal dict with keys: ticker, date, close, volume, avg_volume,
        volume_ratio, high_20d, signal_type, direction. Or None.
    """
    rows = conn.execute(
        """
        SELECT date, close, volume FROM daily_bars
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT 21
        """,
        [ticker],
    ).fetchdf()

    if len(rows) < 21:
        return None

    today = rows.iloc[0]
    window = rows.iloc[1:]  # 20 previous completed bars

    high_20d: float = float(window["close"].max())
    avg_volume: float = float(window["volume"].mean())

    today_close = float(today["close"])
    today_volume = int(today["volume"])

    if today_close <= high_20d:
        return None

    volume_ratio = today_volume / avg_volume
    if volume_ratio < config.VOLUME_RATIO_MIN:
        return None

    today_date = today["date"]
    if hasattr(today_date, "date"):
        today_date = today_date.date()

    logger.info(
        "BREAKOUT | %s | close=%.2f > 20d_high=%.2f | vol_ratio=%.2fx",
        ticker, today_close, high_20d, volume_ratio,
    )
    return {
        "ticker": ticker,
        "date": today_date,
        "close": today_close,
        "volume": today_volume,
        "avg_volume": avg_volume,
        "volume_ratio": volume_ratio,
        "high_20d": high_20d,
        "signal_type": "breakout_20d_high",
        "direction": "bullish",
    }


def scan_all_breakouts(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """
    Two-gate scan: breakout detection followed by momentum confirmation.

    For each ticker:
      1. detect_breakout — if None, skip.
      2. run_momentum_filters — if momentum_pass is False, skip.
      3. Merge both dicts into one signal and append.

    Args:
        conn: DuckDB connection with daily_bars and bars tables populated.

    Returns:
        List of merged signal dicts that passed both gates.
    """
    from signals.momentum import run_momentum_filters  # deferred to avoid circular import

    signals: list[dict[str, Any]] = []
    for ticker in config.ALL_TICKERS:
        breakout = detect_breakout(ticker, conn)
        if breakout is None:
            continue

        momentum = run_momentum_filters(ticker, conn)
        if not momentum["momentum_pass"]:
            continue

        signals.append({**breakout, **momentum})

    return signals
