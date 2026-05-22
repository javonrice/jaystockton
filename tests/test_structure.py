"""
tests/test_structure.py — Tests for signals/structure.py (Session 5).

All tests use synthetic DataFrames — no network calls, no API, no DuckDB.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from signals.structure import (
    check_break_of_structure,
    check_candle_quality,
    check_macd,
    check_rsi_momentum,
    check_trend,
    check_volume,
    detect_structure_breakout,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_df(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    opens: list[float] | None = None,
    volumes: list[int] | None = None,
    start: str = "2020-01-01",
) -> pd.DataFrame:
    """Build a synthetic daily OHLCV DataFrame (ascending by date)."""
    n = len(closes)
    base = datetime.date.fromisoformat(start)
    if highs is None:
        highs = [c + 0.5 for c in closes]
    if lows is None:
        lows = [c - 0.5 for c in closes]
    if opens is None:
        opens = [c - 0.5 for c in closes]
    if volumes is None:
        volumes = [1_000_000] * n
    rows = [
        {
            "date": base + datetime.timedelta(days=i),
            "open": opens[i],
            "high": highs[i],
            "low": lows[i],
            "close": closes[i],
            "volume": volumes[i],
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows)


# ── check_trend ───────────────────────────────────────────────────────────────


class TestTrend:
    def test_trend_pass_price_above_both_emas(self):
        """210-bar ascending series: close > EMA(50) > EMA(200), slope positive → pass."""
        df = _make_df([100.0 + i for i in range(210)])
        result = check_trend(df, 209)
        assert result is not None
        assert result["trend_pass"] is True
        assert result["ema_50"] > result["ema_200"]
        assert float(df.iloc[209]["close"]) > result["ema_50"]

    def test_trend_fail_price_below_50_ema(self):
        """200 ascending bars then sharp drop: close << EMA(50) → trend_pass False."""
        df = _make_df([100.0 + i for i in range(200)] + [50.0])
        result = check_trend(df, 200)
        assert result is not None
        assert result["trend_pass"] is False

    def test_trend_fail_50_ema_below_200_ema(self):
        """210-bar descending series: EMA(50) < EMA(200) → trend_pass False."""
        df = _make_df([310.0 - i for i in range(210)])
        result = check_trend(df, 209)
        assert result is not None
        assert result["trend_pass"] is False
        assert result["ema_50"] < result["ema_200"]

    def test_trend_insufficient_data_returns_none(self):
        """idx < 200 → None (EMA(200) cannot be computed)."""
        df = _make_df([100.0 + i for i in range(205)])
        assert check_trend(df, 150) is None
        assert check_trend(df, 199) is None


# ── check_break_of_structure ──────────────────────────────────────────────────


class TestBOS:
    def _bos_df(self) -> pd.DataFrame:
        """
        25-bar DataFrame with a clear swing high at bar 18 (high=115.5).
        Bars around 18: closes 100..100(×18), 115, 110, 105, 100, 116.
        Search at idx=23 starts from idx-3=20, finds swing high at bar 18.
        """
        closes = [100.0] * 18 + [115.0, 110.0, 105.0, 100.0, 116.0]
        return _make_df(closes)  # idx = 22 (last bar), len=23

    def test_bos_detects_swing_high_correctly(self):
        """Swing high at bar 18 (high=115.5), today close=116 > 115.5 → bos_pass True."""
        closes = [100.0] * 18 + [115.0, 110.0, 105.0, 100.0, 116.0]
        df = _make_df(closes)
        result = check_break_of_structure(df, len(df) - 1)
        assert result is not None
        assert result["bos_pass"] is True
        assert result["swing_high_level"] == pytest.approx(115.5)

    def test_bos_fails_when_close_below_swing_high(self):
        """Same swing high, but today close=110 < 115.5 → bos_pass False."""
        closes = [100.0] * 18 + [115.0, 110.0, 105.0, 100.0, 110.0]
        df = _make_df(closes)
        result = check_break_of_structure(df, len(df) - 1)
        assert result is not None
        assert result["bos_pass"] is False

    def test_bos_requires_swing_high_at_least_3_bars_ago(self):
        """
        Swing high candidate only at idx-2 (not in search range [idx-3, ...]).
        All bars at idx-3 and earlier are flat → no swing high found → None.
        """
        # Flat bars 0..21, spike at idx-2=22 (close=120), then idx-1=23 (110), idx=24 (125)
        closes = [100.0] * 22 + [120.0, 110.0, 125.0]
        df = _make_df(closes)
        # Search range for idx=24: range(21, max(12,2), -1). Bar 22 (idx-2) is NOT checked.
        result = check_break_of_structure(df, len(df) - 1)
        assert result is None


# ── check_volume ──────────────────────────────────────────────────────────────


class TestVolume:
    def test_volume_pass_exceeds_multiplier(self):
        """Today volume = 2× avg → volume_pass True."""
        closes = [100.0] * 25
        vols = [1_000_000] * 24 + [2_000_000]
        df = _make_df(closes, volumes=vols)
        result = check_volume(df, 24)
        assert result is not None
        assert result["volume_pass"] is True
        assert result["volume_ratio"] == pytest.approx(2.0, rel=0.01)

    def test_volume_fail_below_multiplier(self):
        """Today volume = 1.3× avg → volume_pass False (threshold 1.5×)."""
        vols = [1_000_000] * 24 + [1_300_000]
        df = _make_df([100.0] * 25, volumes=vols)
        result = check_volume(df, 24)
        assert result is not None
        assert result["volume_pass"] is False


# ── check_candle_quality ──────────────────────────────────────────────────────


class TestCandleQuality:
    def _bar_df(self, open_: float, high: float, low: float, close: float) -> pd.DataFrame:
        """Single-bar DataFrame for candle tests."""
        return pd.DataFrame([{
            "date": datetime.date(2023, 6, 1),
            "open": open_, "high": high, "low": low,
            "close": close, "volume": 1_000_000,
        }])

    def test_candle_quality_pass_strong_bullish_close(self):
        """
        Bullish, close in top 30%, body >= 40% of range → pass.
        open=100, high=120, low=95, close=118:
          close_position=(118-95)/25=0.92, body=(118-100)/25=0.72, bullish=True.
        """
        result = check_candle_quality(self._bar_df(100.0, 120.0, 95.0, 118.0), 0)
        assert result is not None
        assert result["candle_pass"] is True
        assert result["close_position"] == pytest.approx(0.92, rel=0.01)
        assert result["body_ratio"] == pytest.approx(0.72, rel=0.01)

    def test_candle_quality_fail_doji(self):
        """
        Body only 2% of range → body_ratio < 0.40 → candle_pass False.
        open=109.5, high=120, low=95, close=110: body=0.5/25=0.02.
        """
        result = check_candle_quality(self._bar_df(109.5, 120.0, 95.0, 110.0), 0)
        assert result is not None
        assert result["candle_pass"] is False
        assert result["body_ratio"] < 0.40

    def test_candle_quality_fail_bearish_candle(self):
        """close < open (bearish) → candle_pass False regardless of size."""
        result = check_candle_quality(self._bar_df(115.0, 120.0, 95.0, 105.0), 0)
        assert result is not None
        assert result["candle_pass"] is False


# ── check_rsi_momentum ────────────────────────────────────────────────────────


class TestRSIMomentum:
    def _rsi_df(self, n_ups: int, n_downs: int) -> pd.DataFrame:
        """
        Build a 20-bar DataFrame where the last 15 bars provide the RSI window.
        First 5 bars flat at 100, then n_ups bars up by +1, then n_downs bars down by -1.
        n_ups + n_downs must equal 14 (to fill the 14-period RSI window).
        """
        assert n_ups + n_downs == 14
        closes = [100.0] * 5
        for i in range(1, n_ups + 1):
            closes.append(100.0 + i)
        for i in range(1, n_downs + 1):
            closes.append(100.0 + n_ups - i)
        return _make_df(closes)

    def test_rsi_pass_in_range(self):
        """9 ups + 5 downs → RSI ≈ 64.3 (within 50–70) → rsi_pass True."""
        df = self._rsi_df(9, 5)
        result = check_rsi_momentum(df, len(df) - 1)
        assert result is not None
        assert result["rsi_pass"] is True
        assert 50.0 <= result["rsi_14"] <= 70.0

    def test_rsi_fail_above_70(self):
        """10 ups + 4 downs → RSI ≈ 71.4 (>70) → rsi_pass False."""
        df = self._rsi_df(10, 4)
        result = check_rsi_momentum(df, len(df) - 1)
        assert result is not None
        assert result["rsi_pass"] is False
        assert result["rsi_14"] > 70.0


# ── check_macd ────────────────────────────────────────────────────────────────


class TestMACD:
    def test_macd_pass_positive_and_increasing(self):
        """
        40 flat bars then 6 bars rising by +2/bar.
        Histogram ≈ 1.25 > 0 and > yesterday's ≈ 1.04 → macd_pass True.
        """
        closes = [100.0] * 40 + [100.0 + 2 * (i + 1) for i in range(6)]
        df = _make_df(closes)
        result = check_macd(df, len(df) - 1)
        assert result is not None
        assert result["macd_pass"] is True
        assert result["histogram"] > 0

    def test_macd_fail_negative_histogram(self):
        """Flat series: MACD ≈ 0, histogram = 0 (not > 0) → macd_pass False."""
        df = _make_df([100.0] * 50)
        result = check_macd(df, len(df) - 1)
        assert result is not None
        assert result["macd_pass"] is False

    def test_macd_fail_decreasing_histogram(self):
        """
        40 flat then 25 bars rising by +2/bar.
        At 25 bars in, MACD is positive but histogram is decreasing
        (signal has caught up to MACD) → macd_pass False.
        """
        closes = [100.0] * 40 + [100.0 + 2 * (i + 1) for i in range(25)]
        df = _make_df(closes)
        result = check_macd(df, len(df) - 1)
        assert result is not None
        # Histogram is positive but today < yesterday → macd_pass is False
        assert result["macd_pass"] is False


# ── detect_structure_breakout (combined) ──────────────────────────────────────


_TREND_OK: dict[str, Any] = {
    "ema_50": 110.0, "ema_200": 100.0, "trend_pass": True, "trend_strength": 0.2
}
_BOS_OK: dict[str, Any] = {
    "swing_high_level": 105.0, "swing_high_date": datetime.date(2023, 1, 10),
    "bos_pass": True,
}
_VOL_OK: dict[str, Any] = {"avg_volume": 1_000_000.0, "volume_ratio": 2.0, "volume_pass": True}
_CANDLE_OK: dict[str, Any] = {"close_position": 0.85, "body_ratio": 0.65, "candle_pass": True}
_RSI_OK: dict[str, Any] = {"rsi_14": 62.0, "rsi_pass": True}
_MACD_OK: dict[str, Any] = {
    "macd_line": 1.2, "signal_line": 0.8, "histogram": 0.4, "macd_pass": True
}


def _all_gates_passing():
    """Context manager that patches all 6 gates to return passing results."""
    return (
        patch("signals.structure.check_trend", return_value=_TREND_OK),
        patch("signals.structure.check_break_of_structure", return_value=_BOS_OK),
        patch("signals.structure.check_volume", return_value=_VOL_OK),
        patch("signals.structure.check_candle_quality", return_value=_CANDLE_OK),
        patch("signals.structure.check_rsi_momentum", return_value=_RSI_OK),
        patch("signals.structure.check_macd", return_value=_MACD_OK),
    )


class TestDetectStructureBreakout:
    def _minimal_df(self) -> pd.DataFrame:
        """Minimal DataFrame for combined gate tests (content doesn't matter — gates are mocked)."""
        return _make_df([110.0] * 210, volumes=[2_000_000] * 210)

    def test_all_gates_pass_returns_signal_dict(self):
        """All 6 gates pass → detect_structure_breakout returns a non-None dict."""
        df = self._minimal_df()
        patches = _all_gates_passing()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = detect_structure_breakout(df, 209, ticker="TST")
        assert result is not None
        assert result["signal_type"] == "structure_breakout"
        assert result["direction"] == "bullish"
        assert result["ticker"] == "TST"

    def test_one_gate_fail_returns_none(self):
        """If BOS gate fails, detect_structure_breakout returns None (short-circuit)."""
        df = self._minimal_df()
        bos_fail = {**_BOS_OK, "bos_pass": False}
        patches = _all_gates_passing()
        with patches[0], \
             patch("signals.structure.check_break_of_structure", return_value=bos_fail), \
             patches[2], patches[3], patches[4], patches[5]:
            result = detect_structure_breakout(df, 209)
        assert result is None

    def test_signal_dict_has_all_required_keys(self):
        """Signal dict must contain every key specified in the Session 5 brief."""
        required = {
            "ticker", "date", "close", "volume", "volume_ratio",
            "ema_50", "ema_200", "trend_pass",
            "swing_high_level", "swing_high_date", "bos_pass",
            "candle_pass", "close_position", "body_ratio",
            "rsi_14", "rsi_pass",
            "macd_line", "histogram", "macd_pass",
            "signal_type", "direction",
        }
        df = self._minimal_df()
        patches = _all_gates_passing()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            result = detect_structure_breakout(df, 209, ticker="TST")
        assert result is not None
        assert required == set(result.keys())
