"""
signals/momentum.py — Layer 3: RSI, VWAP, and sector ETF momentum filters.

Three confirmation filters applied after a breakout is detected:
  1. RSI(14) between 50 and 75 — trending but not overbought
  2. Price above today's VWAP — intraday buyers in control
  3. Sector ETF RSI >= 50 — sector tailwind confirmed

Requires:
    daily_bars table for RSI computation.
    bars table (minute bars) for VWAP computation.
    config.SECTOR_MAP, RSI_PERIOD, RSI_MIN, RSI_MAX, VWAP_MIN_BARS.

Returns:
    check_rsi, check_vwap, check_sector_strength, run_momentum_filters.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

import duckdb

import config
from journal.logger import get_logger

logger = get_logger(__name__)


def _compute_rsi(closes: list[float], period: int) -> Optional[float]:
    """
    Compute Wilder's smoothed RSI for the given close price series.

    Args:
        closes: Price series in chronological order (oldest first).
        period: RSI lookback period (typically 14).

    Returns:
        RSI value in [0, 100], or None if insufficient data.
    """
    if len(closes) < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(c, 0.0) for c in changes]
    losses = [abs(min(c, 0.0)) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_gain == 0.0 and avg_loss == 0.0:
        return 50.0
    if avg_loss == 0.0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 4)


def check_rsi(ticker: str, conn: duckdb.DuckDBPyConnection) -> Optional[dict[str, Any]]:
    """
    Compute RSI(14) from daily closes and check if it is in [RSI_MIN, RSI_MAX].

    Args:
        ticker: Stock symbol.
        conn: DuckDB connection with daily_bars populated.

    Returns:
        Dict with rsi_14 and rsi_pass, or None if fewer than 15 bars available.
    """
    rows = conn.execute(
        "SELECT close FROM daily_bars WHERE ticker = ? ORDER BY date DESC LIMIT ?",
        [ticker, config.RSI_PERIOD + 1],
    ).fetchdf()

    if len(rows) < config.RSI_PERIOD + 1:
        return None

    closes = rows["close"].tolist()[::-1]  # reverse to chronological order
    rsi_val = _compute_rsi(closes, config.RSI_PERIOD)
    if rsi_val is None:
        return None

    passed = config.RSI_MIN <= rsi_val <= config.RSI_MAX
    return {"rsi_14": rsi_val, "rsi_pass": passed}


def check_vwap(ticker: str, conn: duckdb.DuckDBPyConnection) -> Optional[dict[str, Any]]:
    """
    Compute today's VWAP from minute bars and check if the last close is above it.

    Args:
        ticker: Stock symbol.
        conn: DuckDB connection with bars (minute bars) populated.

    Returns:
        Dict with vwap and vwap_pass, or None if fewer than VWAP_MIN_BARS today.
    """
    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    rows = conn.execute(
        """
        SELECT close, volume FROM bars
        WHERE ticker = ?
          AND CAST(timestamp AS DATE) = ?
        ORDER BY timestamp ASC
        """,
        [ticker, today],
    ).fetchdf()

    if len(rows) < config.VWAP_MIN_BARS:
        return None

    vwap_val = float((rows["close"] * rows["volume"]).sum() / rows["volume"].sum())
    today_close = float(rows.iloc[-1]["close"])
    passed = today_close > vwap_val
    return {"vwap": vwap_val, "vwap_pass": passed}


def check_sector_strength(ticker: str, conn: duckdb.DuckDBPyConnection) -> Optional[dict[str, Any]]:
    """
    Check the RSI of the ticker's sector ETF. Auto-passes for ETFs and SPY/QQQ.

    Args:
        ticker: Stock symbol.
        conn: DuckDB connection with daily_bars populated.

    Returns:
        Dict with sector_etf, sector_rsi, sector_pass. Returns None if ETF
        data is unavailable. Returns auto-pass dict if ticker maps to None.
    """
    etf = config.SECTOR_MAP.get(ticker)

    if etf is None:
        return {"sector_etf": None, "sector_rsi": None, "sector_pass": True}

    rows = conn.execute(
        "SELECT close FROM daily_bars WHERE ticker = ? ORDER BY date DESC LIMIT ?",
        [etf, config.RSI_PERIOD + 1],
    ).fetchdf()

    if len(rows) < config.RSI_PERIOD + 1:
        return None

    closes = rows["close"].tolist()[::-1]
    etf_rsi = _compute_rsi(closes, config.RSI_PERIOD)
    if etf_rsi is None:
        return None

    passed = etf_rsi >= config.RSI_MIN
    return {"sector_etf": etf, "sector_rsi": etf_rsi, "sector_pass": passed}


def run_momentum_filters(ticker: str, conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """
    Run RSI, VWAP, and sector filters. All three must pass for momentum_pass=True.

    Missing data treatment: RSI/VWAP unavailable → fail (conservative).
    Sector unavailable (no ETF mapping or no ETF data) → auto-pass.

    Args:
        ticker: Stock symbol.
        conn: DuckDB connection with bars and daily_bars populated.

    Returns:
        Dict with individual filter results and momentum_pass boolean.
    """
    rsi_result = check_rsi(ticker, conn)
    vwap_result = check_vwap(ticker, conn)
    sector_result = check_sector_strength(ticker, conn)

    rsi_pass = rsi_result["rsi_pass"] if rsi_result is not None else False
    vwap_pass = vwap_result["vwap_pass"] if vwap_result is not None else False
    sector_pass = sector_result["sector_pass"] if sector_result is not None else True

    return {
        "rsi_14": rsi_result["rsi_14"] if rsi_result else None,
        "rsi_pass": rsi_pass,
        "vwap": vwap_result["vwap"] if vwap_result else None,
        "vwap_pass": vwap_pass,
        "sector_etf": sector_result["sector_etf"] if sector_result else None,
        "sector_rsi": sector_result["sector_rsi"] if sector_result else None,
        "sector_pass": sector_pass,
        "momentum_pass": rsi_pass and vwap_pass and sector_pass,
    }
