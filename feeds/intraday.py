"""
feeds/intraday.py — Pre-market and intraday data fetching for Session 6.

Provides pre-market gap computation, opening range tracking, intraday VWAP,
and the ORB (Opening Range Breakout) signal detector.

All Alpaca calls go through _build_client() so tests can patch it cleanly.
Previous close is sourced from daily_bars table in DuckDB — already populated
by the existing EOD scan.

Requires:
    ALPACA_API_KEY and ALPACA_SECRET_KEY in .env or environment.
    DuckDB connection with daily_bars and bars tables initialised.

Returns:
    fetch_premarket_bars, fetch_intraday_bars,
    compute_premarket_gap, compute_opening_range,
    compute_intraday_vwap, check_orb_signal.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import config
from journal.logger import get_logger

logger = get_logger(__name__)

_ET = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")


def _build_client() -> StockHistoricalDataClient:
    """Authenticated Alpaca client. Isolated for test patching."""
    return StockHistoricalDataClient(
        api_key=config.get_alpaca_api_key(),
        secret_key=config.get_alpaca_secret_key(),
    )


def _today_et() -> datetime.date:
    """Return today's date in US/Eastern time."""
    return datetime.datetime.now(tz=_ET).date()


# ── Data fetching ─────────────────────────────────────────────────────────────


def fetch_premarket_bars(ticker: str) -> Optional[pd.DataFrame]:
    """
    Fetch pre-market minute bars from 4:00 AM to 9:30 AM ET for today.

    Args:
        ticker: Stock symbol.

    Returns:
        DataFrame with columns [ticker, timestamp, open, high, low, close, volume]
        in UTC, or None on any error.
    """
    try:
        today = _today_et()
        start_et = datetime.datetime.combine(
            today, datetime.time(4, 0), tzinfo=_ET
        )
        end_et = datetime.datetime.combine(
            today, datetime.time(9, 30), tzinfo=_ET
        )
        client = _build_client()
        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=start_et,
            end=end_et,
            feed=config.ALPACA_FEED,
        )
        raw = client.get_stock_bars(req).df
        if raw is None or raw.empty:
            logger.debug("No pre-market bars for %s", ticker)
            return None
        raw = raw.reset_index()
        raw.columns = [c.lower() for c in raw.columns]
        raw = raw.rename(columns={"symbol": "ticker"})
        return raw[["ticker", "timestamp", "open", "high", "low", "close", "volume"]].copy()
    except Exception as exc:
        logger.warning("fetch_premarket_bars failed for %s: %s", ticker, exc)
        return None


def fetch_intraday_bars(
    ticker: str, start_time: datetime.datetime
) -> Optional[pd.DataFrame]:
    """
    Fetch minute bars from start_time to now for ticker.

    Args:
        ticker: Stock symbol.
        start_time: Start of the fetch window (timezone-aware).

    Returns:
        DataFrame with columns [ticker, timestamp, open, high, low, close, volume]
        or None on error.
    """
    try:
        client = _build_client()
        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=start_time,
            feed=config.ALPACA_FEED,
        )
        raw = client.get_stock_bars(req).df
        if raw is None or raw.empty:
            return None
        raw = raw.reset_index()
        raw.columns = [c.lower() for c in raw.columns]
        raw = raw.rename(columns={"symbol": "ticker"})
        return raw[["ticker", "timestamp", "open", "high", "low", "close", "volume"]].copy()
    except Exception as exc:
        logger.warning("fetch_intraday_bars failed for %s: %s", ticker, exc)
        return None


def get_prev_close(ticker: str, conn: duckdb.DuckDBPyConnection) -> Optional[float]:
    """
    Return the most recent closing price for ticker from daily_bars table.

    Args:
        ticker: Stock symbol.
        conn: Open DuckDB connection with daily_bars table.

    Returns:
        Float close price, or None if no daily bars exist for ticker.
    """
    try:
        row = conn.execute(
            "SELECT close FROM daily_bars WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            [ticker],
        ).fetchone()
        return float(row[0]) if row else None
    except Exception as exc:
        logger.warning("get_prev_close failed for %s: %s", ticker, exc)
        return None


# ── Computations (pure functions — no network, easily tested) ─────────────────


def compute_premarket_gap(
    ticker: str, prev_close: float, premarket_bars: pd.DataFrame
) -> dict[str, Any]:
    """
    Compute gap statistics from pre-market bar data.

    Args:
        ticker: Stock symbol (for labelling).
        prev_close: Yesterday's closing price.
        premarket_bars: DataFrame of pre-market bars with close, volume columns.

    Returns:
        Dict with keys: ticker, gap_pct, premarket_volume, premarket_high,
        premarket_low, premarket_last, gap_direction.
        gap_pct is (premarket_last - prev_close) / prev_close * 100.
        gap_direction is 'up' | 'down' | 'flat'.
    """
    premarket_last = float(premarket_bars["close"].iloc[-1])
    premarket_high = float(premarket_bars["high"].max())
    premarket_low = float(premarket_bars["low"].min())
    premarket_volume = int(premarket_bars["volume"].sum())

    gap_pct = (premarket_last - prev_close) / prev_close * 100.0 if prev_close else 0.0

    if gap_pct >= 0.5:
        gap_direction = "up"
    elif gap_pct <= -0.5:
        gap_direction = "down"
    else:
        gap_direction = "flat"

    return {
        "ticker": ticker,
        "gap_pct": round(gap_pct, 4),
        "premarket_volume": premarket_volume,
        "premarket_high": round(premarket_high, 4),
        "premarket_low": round(premarket_low, 4),
        "premarket_last": round(premarket_last, 4),
        "gap_direction": gap_direction,
    }


def compute_opening_range(
    bars: pd.DataFrame,
    open_time: datetime.datetime,
    minutes: int = 15,
) -> dict[str, Any]:
    """
    Compute the opening range from the first `minutes` of trading.

    Args:
        bars: DataFrame of intraday bars with timestamp, high, low, volume columns.
        open_time: Market open timestamp (timezone-aware, 9:30 ET).
        minutes: Duration of the opening range window (default 15).

    Returns:
        Dict with keys: or_high, or_low, or_range_pct, or_volume, established.
        established is True only if we have at least `minutes` bars in the window.
    """
    cutoff = open_time + datetime.timedelta(minutes=minutes)
    ts_col = bars["timestamp"]
    if hasattr(ts_col.dtype, "tz") and ts_col.dtype.tz is not None:
        cutoff_aware = cutoff
        if cutoff_aware.tzinfo is None:
            cutoff_aware = cutoff.replace(tzinfo=_UTC)
        window = bars[bars["timestamp"] < cutoff_aware]
    else:
        window = bars[bars["timestamp"] < cutoff.replace(tzinfo=None)]

    if window.empty:
        return {
            "or_high": 0.0, "or_low": 0.0,
            "or_range_pct": 0.0, "or_volume": 0,
            "established": False,
        }

    or_high = float(window["high"].max())
    or_low = float(window["low"].min())
    or_range_pct = (or_high - or_low) / or_low * 100.0 if or_low else 0.0
    or_volume = int(window["volume"].sum())
    established = len(window) >= minutes

    return {
        "or_high": round(or_high, 4),
        "or_low": round(or_low, 4),
        "or_range_pct": round(or_range_pct, 4),
        "or_volume": or_volume,
        "established": established,
    }


def compute_intraday_vwap(bars: pd.DataFrame) -> float:
    """
    Compute VWAP from today's bars.

    VWAP = sum(close * volume) / sum(volume).

    Args:
        bars: DataFrame with close and volume columns.

    Returns:
        VWAP as float, or 0.0 if no bars.
    """
    if bars.empty:
        return 0.0
    total_vol = float(bars["volume"].sum())
    if total_vol == 0:
        return 0.0
    return round(float((bars["close"] * bars["volume"]).sum()) / total_vol, 4)


def check_orb_signal(
    ticker: str,
    bars: pd.DataFrame,
    opening_range: dict[str, Any],
    prev_close: float,
    gap: dict[str, Any],
    spy_prev_close: float = 0.0,
    spy_current_close: float = 0.0,
) -> Optional[dict[str, Any]]:
    """
    Opening Range Breakout signal detector.

    Six gates (all must pass):
        1. Gap >= GAP_MIN_PCT (stock gapped up meaningfully)
        2. ORB established (at least 15 minutes of opening range data)
        3. Current close > or_high (broke above opening range)
        4. Current close > intraday VWAP
        5. Current bar volume > INTRADAY_VOLUME_MULT × avg bar volume in OR
        6. Market context: SPY positive on day (or spy data unavailable → auto-pass)
        + Candle quality: close in top 40% of bar range

    Args:
        ticker: Stock symbol.
        bars: All intraday bars so far today.
        opening_range: Output of compute_opening_range().
        prev_close: Yesterday's closing price for the ticker.
        gap: Output of compute_premarket_gap().
        spy_prev_close: SPY previous close (0.0 → auto-pass market context gate).
        spy_current_close: SPY current intraday close (0.0 → auto-pass).

    Returns:
        Signal dict or None.
    """
    if bars.empty:
        return None

    # Gate 1: gap >= minimum threshold
    if gap.get("gap_pct", 0.0) < config.GAP_MIN_PCT:
        return None

    # Gate 2: opening range established
    if not opening_range.get("established", False):
        return None

    or_high = opening_range["or_high"]
    or_low = opening_range["or_low"]

    current_bar = bars.iloc[-1]
    current_close = float(current_bar["close"])
    current_high = float(current_bar["high"])
    current_low = float(current_bar["low"])
    current_vol = float(current_bar["volume"])

    # Gate 3: close above opening range high
    if current_close <= or_high:
        return None

    # Gate 4: close above VWAP
    vwap = compute_intraday_vwap(bars)
    if vwap > 0 and current_close <= vwap:
        return None

    # Gate 5: volume confirmation vs avg bar volume in opening range
    or_vol = opening_range.get("or_volume", 0)
    or_bars_est = config.ORB_MINUTES  # approximate number of OR bars
    avg_or_bar_vol = (or_vol / or_bars_est) if or_bars_est > 0 else 0
    volume_ratio = current_vol / avg_or_bar_vol if avg_or_bar_vol > 0 else 0.0
    if volume_ratio < config.INTRADAY_VOLUME_MULT:
        return None

    # Gate 6: market context — SPY positive (auto-pass if data unavailable)
    if spy_prev_close > 0 and spy_current_close > 0:
        if spy_current_close <= spy_prev_close:
            return None

    # Candle quality: close in top 40% of bar range
    bar_range = current_high - current_low
    if bar_range > 0:
        close_position = (current_close - current_low) / bar_range
        if close_position < 0.40:
            return None

    current_ts = current_bar["timestamp"]

    return {
        "ticker": ticker,
        "timestamp": current_ts,
        "price": round(current_close, 4),
        "gap_pct": round(gap["gap_pct"], 4),
        "or_high": round(or_high, 4),
        "or_low": round(or_low, 4),
        "vwap": round(vwap, 4),
        "volume_ratio": round(volume_ratio, 4),
        "signal_type": "orb_breakout",
        "direction": "bullish",
        "suggested_stop": round(or_low, 4),
        "premarket_high": round(gap.get("premarket_high", 0.0), 4),
        "premarket_volume": gap.get("premarket_volume", 0),
    }
