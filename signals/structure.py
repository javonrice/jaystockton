"""
signals/structure.py — Session 5: structure-based breakout signal.

Six-gate filter: trend (EMA 50/200), break of structure (swing high),
volume confirmation, candle quality, RSI(14) 50–70, MACD histogram.

EMA and MACD are computed with standard Wilder/exponential formulas so
the module has no dependency on pandas-ta at import time. The package
is still listed in requirements.txt for Codespaces compatibility.

Requires:
    DuckDB connection with daily_bars table for live scanning.

Returns:
    detect_structure_breakout, scan_all_structure_breakouts.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd

import config
from journal.logger import get_logger

logger = get_logger(__name__)

_RSI_PERIOD: int = 14
_RSI_MIN: float = 50.0
_RSI_MAX: float = 70.0
_MACD_FAST: int = 12
_MACD_SLOW: int = 26
_MACD_SIGNAL: int = 9
_MACD_MIN_BARS: int = 35
_EMA_SHORT: int = 50
_EMA_LONG: int = 200
_BOS_LOOKBACK: int = 10
_VOLUME_PERIOD: int = 20
_VOLUME_MULTIPLIER: float = 1.5


# ── Core math helpers ─────────────────────────────────────────────────────────


def _ema_series(values: list[float], period: int) -> list[float]:
    """EMA with SMA initialization. Returns NaN for first period-1 indices."""
    if len(values) < period:
        return [float("nan")] * len(values)
    k = 2.0 / (period + 1)
    result = [float("nan")] * len(values)
    result[period - 1] = sum(values[:period]) / period
    for i in range(period, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1.0 - k)
    return result


def _macd_components(
    closes: list[float],
    fast: int = _MACD_FAST,
    slow: int = _MACD_SLOW,
    signal: int = _MACD_SIGNAL,
) -> Optional[tuple[list[float], list[float], list[float]]]:
    """
    Returns (macd_line, signal_line, histogram) aligned to closes.
    Returns None if fewer than slow+signal-1 values are available.
    """
    if len(closes) < slow + signal - 1:
        return None
    fast_ema = _ema_series(closes, fast)
    slow_ema = _ema_series(closes, slow)

    macd_line = [float("nan")] * len(closes)
    for i in range(slow - 1, len(closes)):
        if not (math.isnan(fast_ema[i]) or math.isnan(slow_ema[i])):
            macd_line[i] = fast_ema[i] - slow_ema[i]

    # Signal = EMA(signal) of the valid MACD values
    macd_pairs = [(i, v) for i, v in enumerate(macd_line) if not math.isnan(v)]
    if len(macd_pairs) < signal:
        return None
    sig_vals = _ema_series([v for _, v in macd_pairs], signal)

    signal_line = [float("nan")] * len(closes)
    histogram = [float("nan")] * len(closes)
    for j, (orig_i, _) in enumerate(macd_pairs):
        if not math.isnan(sig_vals[j]):
            signal_line[orig_i] = sig_vals[j]
            histogram[orig_i] = macd_line[orig_i] - sig_vals[j]

    return macd_line, signal_line, histogram


def _compute_rsi(closes: list[float], period: int) -> Optional[float]:
    """Wilder smoothed RSI. Returns None if insufficient data."""
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


# ── Gate functions ────────────────────────────────────────────────────────────


def check_trend(df: pd.DataFrame, idx: int) -> Optional[dict[str, Any]]:
    """
    EMA(50) and EMA(200) trend filter.

    Pass conditions:
        - close > EMA(50)
        - EMA(50) > EMA(200)
        - EMA(50) slope positive over last 5 days

    Requires at least 200 bars (idx >= 200). Returns None if insufficient.
    """
    if idx < _EMA_LONG:
        return None
    closes = df["close"].iloc[: idx + 1].tolist()
    ema50 = _ema_series(closes, _EMA_SHORT)
    ema200 = _ema_series(closes, _EMA_LONG)

    e50 = ema50[-1]
    e200 = ema200[-1]
    if math.isnan(e50) or math.isnan(e200):
        return None

    # Slope: EMA(50) change over last 5 bars
    if len(ema50) < 6 or math.isnan(ema50[-6]):
        return None
    e50_5d_ago = ema50[-6]
    slope = (e50 - e50_5d_ago) / e50_5d_ago if e50_5d_ago != 0.0 else 0.0

    close = float(df.iloc[idx]["close"])
    trend_pass = bool(close > e50 and e50 > e200 and slope > 0)

    return {
        "ema_50": round(e50, 4),
        "ema_200": round(e200, 4),
        "trend_pass": trend_pass,
        "trend_strength": round(slope * 100, 4),
    }


def check_break_of_structure(
    df: pd.DataFrame, idx: int, lookback: int = _BOS_LOOKBACK
) -> Optional[dict[str, Any]]:
    """
    Most recent swing high in the last lookback bars, at least 3 bars before idx.

    Swing high at bar i: high[i] > high[i-1], high[i-2], high[i+1], high[i+2].
    Pass: today's close > swing high level (the swing high bar's HIGH).
    Returns None if no qualifying swing high found.
    """
    if idx < lookback + 4:
        return None

    n = len(df)
    start = idx - 3
    end = max(idx - lookback - 2, 2)

    swing_high_level: Optional[float] = None
    swing_high_date = None

    for i in range(start, end, -1):
        if i < 2 or i + 2 > n - 1:
            continue
        h_i = float(df.iloc[i]["high"])
        h_im1 = float(df.iloc[i - 1]["high"])
        h_im2 = float(df.iloc[i - 2]["high"])
        h_ip1 = float(df.iloc[i + 1]["high"])
        h_ip2 = float(df.iloc[i + 2]["high"])
        if h_i > h_im1 and h_i > h_im2 and h_i > h_ip1 and h_i > h_ip2:
            swing_high_level = h_i
            swing_high_date = df.iloc[i]["date"]
            break

    if swing_high_level is None:
        return None

    today_close = float(df.iloc[idx]["close"])
    bos_pass = today_close > swing_high_level

    return {
        "swing_high_level": round(swing_high_level, 4),
        "swing_high_date": swing_high_date,
        "bos_pass": bos_pass,
    }


def check_volume(
    df: pd.DataFrame,
    idx: int,
    period: int = _VOLUME_PERIOD,
    multiplier: float = _VOLUME_MULTIPLIER,
) -> Optional[dict[str, Any]]:
    """
    Today volume >= multiplier * avg volume of last period bars (not including today).
    Returns None if insufficient data.
    """
    if idx < period:
        return None
    avg_vol = float(df["volume"].iloc[idx - period: idx].mean())
    if avg_vol == 0:
        return None
    today_vol = float(df.iloc[idx]["volume"])
    vol_ratio = today_vol / avg_vol
    return {
        "avg_volume": round(avg_vol, 2),
        "volume_ratio": round(vol_ratio, 4),
        "volume_pass": bool(vol_ratio >= multiplier),
    }


def check_candle_quality(df: pd.DataFrame, idx: int) -> Optional[dict[str, Any]]:
    """
    Quality bullish breakout candle check.

    Pass conditions:
        - Bullish: close > open
        - Close position (close-low)/(high-low) >= 0.70
        - Body ratio abs(close-open)/(high-low) >= 0.40

    Returns None if candle range is zero.
    """
    bar = df.iloc[idx]
    o = float(bar["open"])
    h = float(bar["high"])
    l = float(bar["low"])
    c = float(bar["close"])
    candle_range = h - l
    if candle_range == 0:
        return None
    close_position = (c - l) / candle_range
    body_ratio = abs(c - o) / candle_range
    bullish = c > o
    candle_pass = bool(bullish and close_position >= 0.70 and body_ratio >= 0.40)
    return {
        "close_position": round(close_position, 4),
        "body_ratio": round(body_ratio, 4),
        "candle_pass": candle_pass,
    }


def check_rsi_momentum(df: pd.DataFrame, idx: int) -> Optional[dict[str, Any]]:
    """
    RSI(14) between 50 and 70 (Wilder smoothing). Returns None if insufficient data.
    """
    if idx < _RSI_PERIOD:
        return None
    closes = df["close"].iloc[idx - _RSI_PERIOD: idx + 1].tolist()
    rsi = _compute_rsi(closes, _RSI_PERIOD)
    if rsi is None:
        return None
    return {
        "rsi_14": rsi,
        "rsi_pass": bool(_RSI_MIN <= rsi <= _RSI_MAX),
    }


def check_macd(df: pd.DataFrame, idx: int) -> Optional[dict[str, Any]]:
    """
    MACD(12, 26, 9) histogram positive and increasing.

    Pass conditions:
        - Histogram > 0  (MACD line above signal line)
        - Histogram today > histogram yesterday  (momentum building)

    Requires at least 35 bars. Returns None if insufficient.
    """
    if idx < _MACD_MIN_BARS:
        return None
    closes = df["close"].iloc[: idx + 1].tolist()
    components = _macd_components(closes)
    if components is None:
        return None
    macd_line, signal_line, histogram = components

    h_today = histogram[-1]
    h_yesterday = histogram[-2] if len(histogram) >= 2 else float("nan")
    if math.isnan(h_today) or math.isnan(h_yesterday):
        return None

    macd_pass = bool(h_today > 0 and h_today > h_yesterday)
    return {
        "macd_line": round(macd_line[-1], 6),
        "signal_line": round(signal_line[-1], 6),
        "histogram": round(h_today, 6),
        "macd_pass": macd_pass,
    }


# ── Combined detector ─────────────────────────────────────────────────────────


def detect_structure_breakout(
    df: pd.DataFrame, idx: int, ticker: str = ""
) -> Optional[dict[str, Any]]:
    """
    Run all 6 gates in order. Short-circuits on first failure.
    Returns merged signal dict or None.

    Signal dict keys:
        ticker, date, close, volume, volume_ratio,
        ema_50, ema_200, trend_pass,
        swing_high_level, swing_high_date, bos_pass,
        candle_pass, close_position, body_ratio,
        rsi_14, rsi_pass,
        macd_line, histogram, macd_pass,
        signal_type, direction
    """
    trend = check_trend(df, idx)
    if trend is None or not trend["trend_pass"]:
        return None

    bos = check_break_of_structure(df, idx)
    if bos is None or not bos["bos_pass"]:
        return None

    vol = check_volume(df, idx)
    if vol is None or not vol["volume_pass"]:
        return None

    candle = check_candle_quality(df, idx)
    if candle is None or not candle["candle_pass"]:
        return None

    rsi = check_rsi_momentum(df, idx)
    if rsi is None or not rsi["rsi_pass"]:
        return None

    macd = check_macd(df, idx)
    if macd is None or not macd["macd_pass"]:
        return None

    bar = df.iloc[idx]
    return {
        "ticker": ticker,
        "date": bar["date"],
        "close": float(bar["close"]),
        "volume": int(bar["volume"]),
        "volume_ratio": vol["volume_ratio"],
        "ema_50": trend["ema_50"],
        "ema_200": trend["ema_200"],
        "trend_pass": trend["trend_pass"],
        "swing_high_level": bos["swing_high_level"],
        "swing_high_date": bos["swing_high_date"],
        "bos_pass": bos["bos_pass"],
        "candle_pass": candle["candle_pass"],
        "close_position": candle["close_position"],
        "body_ratio": candle["body_ratio"],
        "rsi_14": rsi["rsi_14"],
        "rsi_pass": rsi["rsi_pass"],
        "macd_line": macd["macd_line"],
        "histogram": macd["histogram"],
        "macd_pass": macd["macd_pass"],
        "signal_type": "structure_breakout",
        "direction": "bullish",
    }


def scan_all_structure_breakouts(
    tickers: list[str], conn
) -> list[dict[str, Any]]:
    """
    Query daily_bars for each ticker, run detect_structure_breakout on most recent bar.
    Returns list of signal dicts that pass all 6 gates.
    """
    signals: list[dict[str, Any]] = []
    for ticker in tickers:
        try:
            rows = conn.execute(
                "SELECT date, open, high, low, close, volume "
                "FROM daily_bars WHERE ticker = ? ORDER BY date ASC",
                [ticker],
            ).fetchdf()
            if rows.empty or len(rows) < _EMA_LONG + 1:
                continue
            signal = detect_structure_breakout(rows, len(rows) - 1, ticker=ticker)
            if signal is not None:
                signals.append(signal)
        except Exception as exc:
            logger.error(
                "scan_all_structure_breakouts failed for %s: %s", ticker, exc
            )
    return signals
