"""
tests/test_momentum.py — Tests for signals/momentum.py (Session 3).

All tests use in-memory DuckDB — no files created, no Alpaca calls made.
"""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytest

from feeds.market_data import init_daily_bars_table, init_db, store_bars, store_daily_bars
from journal.logger import init_signals_table
from signals.momentum import (
    _compute_rsi,
    check_rsi,
    check_sector_strength,
    check_vwap,
    run_momentum_filters,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fresh_conn():
    conn = init_db(":memory:")
    init_daily_bars_table(conn)
    init_signals_table(conn)
    return conn


def _build_closes(n_ups: int, n_downs: int, base: float = 100.0) -> list[float]:
    """
    Build a 15-element close list (14 periods) with n_ups gains then n_downs losses.

    Requires n_ups + n_downs == 14 so exactly one RSI period fits.
    RSI results are predictable: avg_gain = n_ups/14, avg_loss = n_downs/14.
    """
    assert n_ups + n_downs == 14
    closes = [base]
    for _ in range(n_ups):
        closes.append(closes[-1] + 1.0)
    for _ in range(n_downs):
        closes.append(closes[-1] - 1.0)
    return closes


def _seed_daily_closes(conn, ticker: str, closes: list[float]) -> None:
    """Insert daily_bars rows for ticker using closes in chronological order (oldest first)."""
    today = datetime.date.today()
    n = len(closes)
    rows: list[dict[str, Any]] = [
        {
            "ticker": ticker,
            "date": today - datetime.timedelta(days=(n - 1 - i)),
            "open": c - 1.0, "high": c + 0.5, "low": c - 1.5,
            "close": c, "volume": 100_000,
        }
        for i, c in enumerate(closes)
    ]
    store_daily_bars(conn, pd.DataFrame(rows))


def _seed_minute_bars(
    conn,
    ticker: str,
    closes: list[float],
    volume: int = 10_000,
) -> None:
    """Insert today's minute bars. closes[i] is the close for bar i (oldest first)."""
    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    base_ts = datetime.datetime.combine(
        today, datetime.time(9, 30), tzinfo=datetime.timezone.utc
    )
    rows: list[dict[str, Any]] = [
        {
            "ticker": ticker,
            "timestamp": base_ts + datetime.timedelta(minutes=i),
            "open": c, "high": c + 0.5, "low": c - 0.5, "close": c, "volume": volume,
        }
        for i, c in enumerate(closes)
    ]
    store_bars(conn, pd.DataFrame(rows))


# ── _compute_rsi ──────────────────────────────────────────────────────────────


class TestComputeRSI:
    def test_insufficient_data_returns_none(self):
        """Fewer than period+1 closes → None (need at least 15 for period=14)."""
        assert _compute_rsi([100.0] * 14, 14) is None

    def test_flat_prices_return_50(self):
        """All identical closes → avg_gain=avg_loss=0 → special-case RSI=50."""
        closes = [100.0] * 15
        assert _compute_rsi(closes, 14) == pytest.approx(50.0)

    def test_all_gains_return_100(self):
        """Monotonically rising prices → avg_loss=0 → RSI=100."""
        closes = [float(i) for i in range(15)]
        assert _compute_rsi(closes, 14) == pytest.approx(100.0)

    def test_all_losses_return_0(self):
        """Monotonically falling prices → avg_gain=0, rs=0 → RSI=0."""
        closes = [float(14 - i) for i in range(15)]
        assert _compute_rsi(closes, 14) == pytest.approx(0.0)

    def test_mixed_gives_expected_value(self):
        """9 ups + 5 downs → rs=1.8 → RSI≈64.3 (between 50 and 75)."""
        closes = _build_closes(9, 5)
        result = _compute_rsi(closes, 14)
        assert result is not None
        assert 60.0 < result < 70.0


# ── check_rsi ─────────────────────────────────────────────────────────────────


class TestCheckRSI:
    def test_returns_none_for_unknown_ticker(self):
        """No bars in DB → None."""
        conn = _fresh_conn()
        assert check_rsi("FAKE", conn) is None

    def test_returns_none_with_insufficient_bars(self):
        """Fewer than RSI_PERIOD+1=15 daily bars → None."""
        conn = _fresh_conn()
        _seed_daily_closes(conn, "AAPL", [100.0] * 10)
        assert check_rsi("AAPL", conn) is None

    def test_rsi_in_range_passes(self):
        """9 ups + 5 downs → RSI≈64 → rsi_pass=True."""
        conn = _fresh_conn()
        _seed_daily_closes(conn, "AAPL", _build_closes(9, 5))
        result = check_rsi("AAPL", conn)
        assert result is not None
        assert result["rsi_pass"] is True
        assert 50.0 <= result["rsi_14"] <= 75.0

    def test_rsi_above_max_fails(self):
        """12 ups + 2 downs → RSI≈86 → rsi_pass=False (above RSI_MAX=75)."""
        conn = _fresh_conn()
        _seed_daily_closes(conn, "AAPL", _build_closes(12, 2))
        result = check_rsi("AAPL", conn)
        assert result is not None
        assert result["rsi_pass"] is False
        assert result["rsi_14"] > 75.0

    def test_rsi_below_min_fails(self):
        """4 ups + 10 downs → RSI≈29 → rsi_pass=False (below RSI_MIN=50)."""
        conn = _fresh_conn()
        _seed_daily_closes(conn, "AAPL", _build_closes(4, 10))
        result = check_rsi("AAPL", conn)
        assert result is not None
        assert result["rsi_pass"] is False
        assert result["rsi_14"] < 50.0

    def test_result_keys(self):
        """Return dict has exactly rsi_14 and rsi_pass."""
        conn = _fresh_conn()
        _seed_daily_closes(conn, "AAPL", _build_closes(9, 5))
        result = check_rsi("AAPL", conn)
        assert result is not None
        assert set(result.keys()) == {"rsi_14", "rsi_pass"}


# ── check_vwap ────────────────────────────────────────────────────────────────


class TestCheckVWAP:
    def test_returns_none_for_unknown_ticker(self):
        """No minute bars → None."""
        conn = _fresh_conn()
        assert check_vwap("FAKE", conn) is None

    def test_returns_none_with_insufficient_bars(self):
        """Fewer than VWAP_MIN_BARS=30 minute bars → None."""
        conn = _fresh_conn()
        _seed_minute_bars(conn, "AAPL", [100.0] * 20)
        assert check_vwap("AAPL", conn) is None

    def test_vwap_pass_when_close_above(self):
        """29 bars at 100, last bar at 200 → last_close > vwap → vwap_pass=True."""
        conn = _fresh_conn()
        closes = [100.0] * 29 + [200.0]
        _seed_minute_bars(conn, "AAPL", closes)
        result = check_vwap("AAPL", conn)
        assert result is not None
        assert result["vwap_pass"] is True
        assert result["vwap"] < 200.0

    def test_vwap_fail_when_close_below(self):
        """29 bars at 200, last bar at 100 → last_close < vwap → vwap_pass=False."""
        conn = _fresh_conn()
        closes = [200.0] * 29 + [100.0]
        _seed_minute_bars(conn, "AAPL", closes)
        result = check_vwap("AAPL", conn)
        assert result is not None
        assert result["vwap_pass"] is False

    def test_vwap_value_uniform_closes(self):
        """All closes equal → VWAP equals that close."""
        conn = _fresh_conn()
        _seed_minute_bars(conn, "MSFT", [150.0] * 30, volume=5_000)
        result = check_vwap("MSFT", conn)
        assert result is not None
        assert result["vwap"] == pytest.approx(150.0)


# ── check_sector_strength ─────────────────────────────────────────────────────


class TestCheckSectorStrength:
    def test_auto_pass_when_ticker_maps_to_none(self):
        """SPY maps to None in SECTOR_MAP → sector_pass=True without any DB query."""
        conn = _fresh_conn()
        result = check_sector_strength("SPY", conn)
        assert result is not None
        assert result["sector_pass"] is True
        assert result["sector_etf"] is None
        assert result["sector_rsi"] is None

    def test_returns_none_when_etf_data_missing(self):
        """AAPL maps to XLK but no XLK daily bars → None (conservative: no data = no pass)."""
        conn = _fresh_conn()
        result = check_sector_strength("AAPL", conn)
        assert result is None

    def test_sector_passes_when_etf_rsi_above_min(self):
        """AAPL → XLK; seed XLK with RSI≈64 → sector_pass=True."""
        conn = _fresh_conn()
        _seed_daily_closes(conn, "XLK", _build_closes(9, 5))
        result = check_sector_strength("AAPL", conn)
        assert result is not None
        assert result["sector_pass"] is True
        assert result["sector_etf"] == "XLK"
        assert result["sector_rsi"] is not None

    def test_sector_fails_when_etf_rsi_below_min(self):
        """AAPL → XLK; seed XLK with RSI≈29 → sector_pass=False."""
        conn = _fresh_conn()
        _seed_daily_closes(conn, "XLK", _build_closes(4, 10))
        result = check_sector_strength("AAPL", conn)
        assert result is not None
        assert result["sector_pass"] is False


# ── run_momentum_filters ──────────────────────────────────────────────────────


class TestRunMomentumFilters:
    def test_result_contains_all_required_keys(self):
        """run_momentum_filters always returns all 8 keys regardless of data availability."""
        conn = _fresh_conn()
        result = run_momentum_filters("AAPL", conn)
        assert set(result.keys()) == {
            "rsi_14", "rsi_pass", "vwap", "vwap_pass",
            "sector_etf", "sector_rsi", "sector_pass", "momentum_pass",
        }

    def test_missing_rsi_fails_momentum(self):
        """No daily bars → rsi=None → rsi_pass=False → momentum_pass=False."""
        conn = _fresh_conn()
        result = run_momentum_filters("AAPL", conn)
        assert result["momentum_pass"] is False
        assert result["rsi_14"] is None
        assert result["rsi_pass"] is False

    def test_missing_vwap_fails_momentum(self):
        """RSI passes but no minute bars → vwap=None → vwap_pass=False → momentum_pass=False."""
        conn = _fresh_conn()
        _seed_daily_closes(conn, "SPY", _build_closes(9, 5))
        result = run_momentum_filters("SPY", conn)
        assert result["momentum_pass"] is False
        assert result["vwap"] is None
        assert result["vwap_pass"] is False

    def test_all_filters_pass_for_spy(self):
        """SPY with RSI≈64 + last_close > vwap + sector=auto-pass → momentum_pass=True."""
        conn = _fresh_conn()
        _seed_daily_closes(conn, "SPY", _build_closes(9, 5))
        _seed_minute_bars(conn, "SPY", [100.0] * 29 + [200.0])
        result = run_momentum_filters("SPY", conn)
        assert result["momentum_pass"] is True
        assert result["rsi_pass"] is True
        assert result["vwap_pass"] is True
        assert result["sector_pass"] is True

    def test_sector_unavailable_auto_passes(self):
        """Missing sector ETF data → sector_pass=True (conservative auto-pass for sector)."""
        conn = _fresh_conn()
        result = run_momentum_filters("AAPL", conn)
        assert result["sector_pass"] is True
