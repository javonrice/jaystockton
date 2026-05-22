"""
tests/test_signals.py — Tests for signals/breakout.py (Sessions 2+3).

All tests use in-memory DuckDB — no files created, no Alpaca calls made.
"""

from __future__ import annotations

import datetime
from typing import Any

import duckdb
import pandas as pd
import pytest

from feeds.market_data import init_daily_bars_table, init_db, store_bars, store_daily_bars
from journal.logger import init_signals_table, store_signal
from signals.breakout import detect_breakout, scan_all_breakouts


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fresh_conn() -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection with all Session 1-3 tables."""
    conn = init_db(":memory:")          # creates bars table
    init_daily_bars_table(conn)
    init_signals_table(conn)
    return conn


def _make_daily_bars(
    ticker: str,
    n_bars: int,
    today_close: float,
    today_volume: int,
    window_close: float,
    window_volume: int,
) -> pd.DataFrame:
    """
    Build a synthetic daily_bars DataFrame.

    The first row is 'today'; subsequent rows are the lookback window.
    All window bars share the same close/volume so thresholds are predictable.
    """
    today = datetime.date.today()
    rows: list[dict[str, Any]] = [
        {
            "ticker": ticker,
            "date": today,
            "open": today_close - 1.0,
            "high": today_close + 0.5,
            "low": today_close - 1.5,
            "close": today_close,
            "volume": today_volume,
        }
    ]
    for i in range(1, n_bars):
        rows.append(
            {
                "ticker": ticker,
                "date": today - datetime.timedelta(days=i),
                "open": window_close - 1.0,
                "high": window_close + 0.5,
                "low": window_close - 1.5,
                "close": window_close,
                "volume": window_volume,
            }
        )
    return pd.DataFrame(rows)


def _seed(conn: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> None:
    store_daily_bars(conn, df)


def _seed_minute_bars(
    conn: duckdb.DuckDBPyConnection,
    ticker: str,
    n_bars: int = 30,
    base_close: float = 100.0,
    last_close: float = 200.0,
    volume: int = 10_000,
) -> None:
    """Insert n_bars minute bars for today. Last bar has last_close; the rest use base_close."""
    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    base_ts = datetime.datetime.combine(
        today, datetime.time(9, 30), tzinfo=datetime.timezone.utc
    )
    rows: list[dict[str, Any]] = []
    for i in range(n_bars - 1):
        c = base_close
        rows.append({
            "ticker": ticker,
            "timestamp": base_ts + datetime.timedelta(minutes=i),
            "open": c, "high": c + 0.5, "low": c - 0.5, "close": c, "volume": volume,
        })
    c = last_close
    rows.append({
        "ticker": ticker,
        "timestamp": base_ts + datetime.timedelta(minutes=n_bars - 1),
        "open": c, "high": c + 0.5, "low": c - 0.5, "close": c, "volume": volume,
    })
    store_bars(conn, pd.DataFrame(rows))


# ── detect_breakout() ─────────────────────────────────────────────────────────


class TestDetectBreakout:
    def test_no_signal_when_close_not_new_high(self):
        """Close equals the 20d high (not strictly greater) → None."""
        conn = _fresh_conn()
        # today_close == window_close → equals but does not exceed
        df = _make_daily_bars("AAPL", 21, today_close=100.0, today_volume=200_000,
                               window_close=100.0, window_volume=100_000)
        _seed(conn, df)
        assert detect_breakout("AAPL", conn) is None

    def test_no_signal_when_volume_insufficient(self):
        """New closing high but volume only 1.3x average → None."""
        conn = _fresh_conn()
        df = _make_daily_bars("AAPL", 21, today_close=101.0, today_volume=130_000,
                               window_close=100.0, window_volume=100_000)
        _seed(conn, df)
        assert detect_breakout("AAPL", conn) is None

    def test_signal_fires_when_both_conditions_met(self):
        """New closing high + 2x volume → returns a signal dict."""
        conn = _fresh_conn()
        df = _make_daily_bars("AAPL", 21, today_close=101.0, today_volume=200_000,
                               window_close=100.0, window_volume=100_000)
        _seed(conn, df)
        result = detect_breakout("AAPL", conn)
        assert result is not None

    def test_signal_dict_has_all_required_keys(self):
        """Signal dict must contain every specified key with correct types."""
        conn = _fresh_conn()
        df = _make_daily_bars("AAPL", 21, today_close=101.0, today_volume=200_000,
                               window_close=100.0, window_volume=100_000)
        _seed(conn, df)
        result = detect_breakout("AAPL", conn)
        assert result is not None

        required = {"ticker", "date", "close", "volume", "avg_volume",
                    "volume_ratio", "high_20d", "signal_type", "direction"}
        assert required == set(result.keys())

        assert isinstance(result["ticker"], str)
        assert isinstance(result["date"], datetime.date)
        assert isinstance(result["close"], float)
        assert isinstance(result["volume"], int)
        assert isinstance(result["avg_volume"], float)
        assert isinstance(result["volume_ratio"], float)
        assert isinstance(result["high_20d"], float)
        assert result["signal_type"] == "breakout_20d_high"
        assert result["direction"] == "bullish"

    def test_signal_values_are_correct(self):
        """volume_ratio and high_20d values match expected calculations."""
        conn = _fresh_conn()
        df = _make_daily_bars("AAPL", 21, today_close=105.0, today_volume=300_000,
                               window_close=100.0, window_volume=100_000)
        _seed(conn, df)
        result = detect_breakout("AAPL", conn)
        assert result is not None
        assert result["high_20d"] == pytest.approx(100.0)
        assert result["avg_volume"] == pytest.approx(100_000.0)
        assert result["volume_ratio"] == pytest.approx(3.0)

    def test_insufficient_data_returns_none(self):
        """Fewer than 21 bars → None, no exception raised."""
        conn = _fresh_conn()
        df = _make_daily_bars("AAPL", 10, today_close=101.0, today_volume=200_000,
                               window_close=100.0, window_volume=100_000)
        _seed(conn, df)
        assert detect_breakout("AAPL", conn) is None

    def test_no_data_returns_none(self):
        """Ticker with zero bars in DB → None, no exception."""
        conn = _fresh_conn()
        assert detect_breakout("AAPL", conn) is None

    def test_exactly_21_bars_fires_signal(self):
        """Exactly 21 bars (minimum required) → signal fires if conditions met."""
        conn = _fresh_conn()
        df = _make_daily_bars("MSFT", 21, today_close=101.0, today_volume=200_000,
                               window_close=100.0, window_volume=100_000)
        _seed(conn, df)
        result = detect_breakout("MSFT", conn)
        assert result is not None


# ── store_signal() + duplicate handling ───────────────────────────────────────


class TestStoreSignal:
    def _make_signal(self, ticker: str = "AAPL") -> dict[str, Any]:
        return {
            "ticker": ticker,
            "date": datetime.date.today(),
            "signal_type": "breakout_20d_high",
            "direction": "bullish",
            "close": 101.0,
            "volume": 200_000,
            "avg_volume": 100_000.0,
            "volume_ratio": 2.0,
            "high_20d": 100.0,
        }

    def test_duplicate_signal_not_stored(self):
        """Storing the same (ticker, date, signal_type) twice → only 1 row in DB."""
        conn = _fresh_conn()
        sig = self._make_signal()
        store_signal(conn, sig)
        store_signal(conn, sig)
        count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        assert count == 1

    def test_different_tickers_both_stored(self):
        """Two signals for different tickers on the same date → 2 rows."""
        conn = _fresh_conn()
        store_signal(conn, self._make_signal("AAPL"))
        store_signal(conn, self._make_signal("MSFT"))
        count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        assert count == 2


# ── scan_all_breakouts() ──────────────────────────────────────────────────────


class TestScanAllBreakouts:
    def test_returns_empty_list_when_no_signals(self):
        """No tickers have sufficient data → empty list, no exception."""
        conn = _fresh_conn()
        result = scan_all_breakouts(conn)
        assert result == []

    def test_returns_signal_for_qualifying_ticker(self):
        """SPY passes breakout + all momentum gates → one signal in returned list.

        Close series design (21 bars, oldest→newest):
          bars 1-6  : 100 (anchor 20d high at 108 without crowding RSI window)
          bars 7-15 : 100→108 (8 up-moves)
          bars 16-20: 107→103 (5 down-moves)
          bar 21    : 109 > 20d_high=108 → breakout fires
        15-bar RSI window: 8 gains of 1 + 5 losses of 1 + final gain of 6
          → avg_gain=1.0, avg_loss=5/14, rs=2.8, RSI≈73.7 (passes 50–75).
        VWAP: 29 bars at 490, last bar at 600 → last_close > vwap.
        Sector: SPY→None in SECTOR_MAP → auto-pass.
        """
        conn = _fresh_conn()
        today = datetime.date.today()
        closes = (
            [100.0] * 6
            + [float(100 + i) for i in range(9)]   # 100..108
            + [float(107 - i) for i in range(5)]   # 107..103
            + [109.0]                               # today
        )
        rows = [
            {
                "ticker": "SPY",
                "date": today - datetime.timedelta(days=(20 - i)),
                "open": c - 1.0, "high": c + 0.5, "low": c - 1.5,
                "close": c,
                "volume": 100_000_000 if i == 20 else 50_000_000,
            }
            for i, c in enumerate(closes)
        ]
        store_daily_bars(conn, pd.DataFrame(rows))
        _seed_minute_bars(conn, "SPY", n_bars=30, base_close=490.0, last_close=600.0)
        results = scan_all_breakouts(conn)
        tickers = [s["ticker"] for s in results]
        assert "SPY" in tickers


# ── store_daily_bars() deduplication ─────────────────────────────────────────


class TestDailyBarDedup:
    def test_daily_bar_dedup(self):
        """Inserting the same daily bar twice → second insert stores 0 rows."""
        conn = _fresh_conn()
        df = _make_daily_bars("SPY", 5, today_close=500.0, today_volume=50_000_000,
                               window_close=498.0, window_volume=45_000_000)
        first = store_daily_bars(conn, df)
        second = store_daily_bars(conn, df)
        assert first == 5
        assert second == 0
        count = conn.execute("SELECT COUNT(*) FROM daily_bars WHERE ticker='SPY'").fetchone()[0]
        assert count == 5
