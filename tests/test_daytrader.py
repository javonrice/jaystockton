"""
tests/test_daytrader.py — Tests for feeds/intraday.py and signals/daytrader.py (Session 6).

All tests use synthetic DataFrames and mocked Alpaca calls — no network, no API keys.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from feeds.intraday import (
    check_orb_signal,
    compute_intraday_vwap,
    compute_opening_range,
    compute_premarket_gap,
)
from signals.daytrader import build_discord_message


# ── Helpers ───────────────────────────────────────────────────────────────────

_OPEN_ET = datetime.datetime(2023, 6, 15, 13, 30, 0,
                              tzinfo=datetime.timezone.utc)  # 9:30 ET = 13:30 UTC


def _make_bars(
    closes: list[float],
    volumes: list[int] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    base_ts: datetime.datetime | None = None,
    interval_minutes: int = 1,
) -> pd.DataFrame:
    """Build a synthetic intraday bar DataFrame with UTC timestamps."""
    n = len(closes)
    if volumes is None:
        volumes = [100_000] * n
    if highs is None:
        highs = [c + 0.5 for c in closes]
    if lows is None:
        lows = [c - 0.5 for c in closes]
    if base_ts is None:
        base_ts = datetime.datetime(2023, 6, 15, 13, 30, 0,  # 9:30 ET = 13:30 UTC
                                    tzinfo=datetime.timezone.utc)
    rows = [
        {
            "ticker": "TST",
            "timestamp": base_ts + datetime.timedelta(minutes=i * interval_minutes),
            "open": closes[i] - 0.2,
            "high": highs[i],
            "low": lows[i],
            "close": closes[i],
            "volume": volumes[i],
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows)


def _make_gap(
    gap_pct: float = 3.0,
    premarket_high: float = 105.0,
    premarket_volume: int = 500_000,
) -> dict[str, Any]:
    """Build a synthetic gap dict as returned by compute_premarket_gap."""
    return {
        "ticker": "TST",
        "gap_pct": gap_pct,
        "premarket_volume": premarket_volume,
        "premarket_high": premarket_high,
        "premarket_low": 102.0,
        "premarket_last": 104.0,
        "gap_direction": "up" if gap_pct > 0 else "down",
    }


def _make_or(
    or_high: float = 103.0,
    or_low: float = 100.0,
    or_volume: int = 1_500_000,
    established: bool = True,
) -> dict[str, Any]:
    """Build a synthetic opening range dict."""
    return {
        "or_high": or_high,
        "or_low": or_low,
        "or_range_pct": round((or_high - or_low) / or_low * 100, 4),
        "or_volume": or_volume,
        "established": established,
    }


# ── compute_premarket_gap ─────────────────────────────────────────────────────


class TestComputePremarketGap:
    def test_gap_computes_correctly(self):
        """prev_close=100, premarket_last=103 → gap_pct=3.0."""
        bars = _make_bars([101.0, 102.0, 103.0], volumes=[10_000, 12_000, 15_000])
        result = compute_premarket_gap("TST", 100.0, bars)
        assert result["gap_pct"] == pytest.approx(3.0, rel=0.01)
        assert result["ticker"] == "TST"

    def test_gap_direction_up(self):
        """Positive gap → direction 'up'."""
        bars = _make_bars([103.0])
        result = compute_premarket_gap("TST", 100.0, bars)
        assert result["gap_direction"] == "up"

    def test_gap_below_threshold_not_candidate(self):
        """1.5% gap is below GAP_MIN_PCT=2.0 — gap is computed but caller filters."""
        bars = _make_bars([101.5])
        result = compute_premarket_gap("TST", 100.0, bars)
        assert result["gap_pct"] == pytest.approx(1.5, rel=0.01)
        # Caller (scan_premarket_gaps) does the threshold filter; function just computes
        import config
        assert result["gap_pct"] < config.GAP_MIN_PCT


# ── compute_opening_range ─────────────────────────────────────────────────────


class TestComputeOpeningRange:
    def test_opening_range_high_low_correct(self):
        """15 bars → or_high = max high, or_low = min low, established=True."""
        closes = [100.0 + i * 0.1 for i in range(20)]
        highs = [c + 2.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        bars = _make_bars(closes, highs=highs, lows=lows)
        or_result = compute_opening_range(bars, _OPEN_ET, minutes=15)
        assert or_result["established"] is True
        assert or_result["or_high"] == pytest.approx(max(highs[:15]), rel=0.01)
        assert or_result["or_low"] == pytest.approx(min(lows[:15]), rel=0.01)

    def test_opening_range_not_established_under_15_bars(self):
        """10 bars → established=False (fewer than the required 15-minute window)."""
        bars = _make_bars([100.0] * 10)
        or_result = compute_opening_range(bars, _OPEN_ET, minutes=15)
        assert or_result["established"] is False


# ── compute_intraday_vwap ─────────────────────────────────────────────────────


class TestComputeIntradayVWAP:
    def test_vwap_computes_correctly(self):
        """VWAP = sum(close * volume) / sum(volume)."""
        # close=100, vol=1000 and close=110, vol=2000 → VWAP = (100000+220000)/3000 ≈ 106.67
        bars = _make_bars([100.0, 110.0], volumes=[1_000, 2_000])
        vwap = compute_intraday_vwap(bars)
        expected = (100.0 * 1_000 + 110.0 * 2_000) / 3_000
        assert vwap == pytest.approx(expected, rel=0.001)

    def test_vwap_empty_bars_returns_zero(self):
        """Empty DataFrame → 0.0, no exception."""
        assert compute_intraday_vwap(pd.DataFrame()) == 0.0


# ── check_orb_signal ─────────────────────────────────────────────────────────


def _all_pass_bars() -> pd.DataFrame:
    """
    20 bars where the last bar breaks above the OR high (103.0).
    VWAP ≈ 102.5 (below close=105). Volume 3x the OR avg.
    Close at 104.5 (high=106, low=104) → close_position=(105-104)/2=0.5 >= 0.40.
    """
    # 15 OR bars at 101 (below or_high=103), then 5 bars rising
    closes = [101.0] * 15 + [102.0, 102.5, 103.5, 104.0, 105.0]
    vols = [100_000] * 15 + [100_000, 100_000, 100_000, 100_000, 450_000]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    return _make_bars(closes, volumes=vols, highs=highs, lows=lows)


class TestCheckOrbSignal:
    def test_orb_signal_fires_all_conditions_met(self):
        """All 6 gates pass → signal dict returned with correct keys."""
        bars = _all_pass_bars()
        or_data = _make_or(or_high=103.0, or_low=100.0, or_volume=1_500_000)
        gap = _make_gap(gap_pct=3.0)
        result = check_orb_signal(
            ticker="TST", bars=bars, opening_range=or_data,
            prev_close=100.0, gap=gap,
        )
        assert result is not None
        assert result["signal_type"] == "orb_breakout"
        assert result["direction"] == "bullish"
        assert result["ticker"] == "TST"

    def test_orb_no_signal_gap_too_small(self):
        """gap_pct=1.5 < GAP_MIN_PCT=2.0 → None."""
        bars = _all_pass_bars()
        or_data = _make_or(or_high=103.0, or_low=100.0)
        gap = _make_gap(gap_pct=1.5)
        result = check_orb_signal(
            ticker="TST", bars=bars, opening_range=or_data,
            prev_close=100.0, gap=gap,
        )
        assert result is None

    def test_orb_no_signal_price_below_or_high(self):
        """Current close=102 < or_high=103 → None (gate 3 fails)."""
        closes = [101.0] * 15 + [101.5, 102.0, 102.0, 102.0, 102.0]
        vols = [100_000] * 20
        bars = _make_bars(closes, volumes=vols)
        or_data = _make_or(or_high=103.0, or_low=100.0)
        gap = _make_gap(gap_pct=3.0)
        result = check_orb_signal(
            ticker="TST", bars=bars, opening_range=or_data,
            prev_close=100.0, gap=gap,
        )
        assert result is None

    def test_orb_no_signal_below_vwap(self):
        """Price above OR high but below VWAP → None (gate 4 fails)."""
        # Close=104 above or_high=103, but heavy volume on early bars pulls VWAP up
        # Make early bars have close=120 and high volume → VWAP >> 104
        closes = [120.0] * 15 + [104.0] * 5
        vols = [1_000_000] * 15 + [100_000] * 5
        bars = _make_bars(closes, volumes=vols)
        or_data = _make_or(or_high=103.0, or_low=100.0)
        gap = _make_gap(gap_pct=3.0)
        result = check_orb_signal(
            ticker="TST", bars=bars, opening_range=or_data,
            prev_close=100.0, gap=gap,
        )
        assert result is None

    def test_orb_stop_is_or_low(self):
        """suggested_stop in signal equals the opening range low."""
        bars = _all_pass_bars()
        or_low = 98.5
        or_data = _make_or(or_high=103.0, or_low=or_low)
        gap = _make_gap(gap_pct=3.0)
        result = check_orb_signal(
            ticker="TST", bars=bars, opening_range=or_data,
            prev_close=100.0, gap=gap,
        )
        assert result is not None
        assert result["suggested_stop"] == pytest.approx(or_low)


# ── build_discord_message ─────────────────────────────────────────────────────


class TestBuildDiscordMessage:
    def _sample_signal(self) -> dict[str, Any]:
        return {
            "ticker": "COIN",
            "timestamp": datetime.datetime(2023, 6, 15, 14, 47, 0,
                                           tzinfo=datetime.timezone.utc),
            "price": 318.40,
            "gap_pct": 4.2,
            "or_high": 315.20,
            "or_low": 308.50,
            "vwap": 311.80,
            "volume_ratio": 2.4,
            "signal_type": "orb_breakout",
            "direction": "bullish",
            "suggested_stop": 308.50,
            "premarket_high": 312.50,
            "premarket_volume": 1_200_000,
        }

    def test_discord_message_format(self):
        """Message contains ticker, price, gap and the ORB keyword."""
        msg = build_discord_message(self._sample_signal())
        assert "COIN" in msg
        assert "318.40" in msg
        assert "4.2" in msg
        assert "ORB" in msg.upper() or "SIGNAL" in msg.upper()

    def test_discord_message_contains_stop(self):
        """Stop level appears in the message."""
        msg = build_discord_message(self._sample_signal())
        assert "308.50" in msg

    def test_discord_message_contains_vwap(self):
        """VWAP price appears in the message."""
        msg = build_discord_message(self._sample_signal())
        assert "311.80" in msg


# ── send_discord_alert (edge case) ───────────────────────────────────────────


class TestSendDiscordAlert:
    def test_send_discord_alert_handles_missing_webhook(self):
        """Empty DISCORD_WEBHOOK_URL → returns False, no exception raised."""
        from alerts.discord import send_discord_alert
        with patch("config.DISCORD_WEBHOOK_URL", ""):
            result = send_discord_alert("test message")
        assert result is False
