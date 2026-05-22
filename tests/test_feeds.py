"""
tests/test_feeds.py — Tests for feeds/market_data.py.

All Alpaca API calls are mocked — tests run fully offline.
DuckDB uses in-memory databases (':memory:') — no files created.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from feeds.market_data import (
    fetch_bars,
    init_db,
    is_market_open,
    store_bars,
)

_ET = ZoneInfo("America/New_York")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _et(weekday: int, hour: int, minute: int) -> datetime.datetime:
    """Build an Eastern Time datetime for a given weekday offset from 2025-01-06 (Monday)."""
    base = datetime.date(2025, 1, 6)
    d = base + datetime.timedelta(days=weekday)
    return datetime.datetime(d.year, d.month, d.day, hour, minute, tzinfo=_ET)


def _bars_df(tickers: list[str] | None = None, n: int = 3) -> pd.DataFrame:
    """Build a minimal valid bars DataFrame for DB tests."""
    if tickers is None:
        tickers = ["AAPL"] * n
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    rows = [
        {
            "ticker": t,
            "timestamp": now - datetime.timedelta(minutes=i),
            "open": 150.0 + i,
            "high": 151.0 + i,
            "low": 149.0 + i,
            "close": 150.5 + i,
            "volume": 1000 + i * 100,
        }
        for i, t in enumerate(tickers)
    ]
    return pd.DataFrame(rows)


def _mock_alpaca_response(ticker: str, n: int) -> MagicMock:
    """Build a mock StockBarsResponse whose .df resembles alpaca-py's MultiIndex output."""
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    idx = pd.MultiIndex.from_tuples(
        [(ticker, now - datetime.timedelta(minutes=i)) for i in range(n)],
        names=["symbol", "timestamp"],
    )
    df = pd.DataFrame(
        {
            "open": [150.0 + i for i in range(n)],
            "high": [151.0 + i for i in range(n)],
            "low": [149.0 + i for i in range(n)],
            "close": [150.5 + i for i in range(n)],
            "volume": [1000 + i * 100 for i in range(n)],
            "trade_count": [10] * n,
            "vwap": [150.2 + i for i in range(n)],
        },
        index=idx,
    )
    mock = MagicMock()
    mock.df = df
    return mock


# ── is_market_open() ──────────────────────────────────────────────────────────


class TestIsMarketOpen:
    def test_open_on_tuesday_at_1000(self):
        with patch("feeds.market_data._now_et", return_value=_et(1, 10, 0)):
            assert is_market_open() is True

    def test_open_at_exactly_0930(self):
        with patch("feeds.market_data._now_et", return_value=_et(0, 9, 30)):
            assert is_market_open() is True

    def test_closed_at_0929(self):
        with patch("feeds.market_data._now_et", return_value=_et(0, 9, 29)):
            assert is_market_open() is False

    def test_closed_at_exactly_1600(self):
        # 16:00 is the close — the interval is [9:30, 16:00), so 16:00 is closed.
        with patch("feeds.market_data._now_et", return_value=_et(0, 16, 0)):
            assert is_market_open() is False

    def test_closed_after_close(self):
        with patch("feeds.market_data._now_et", return_value=_et(1, 17, 0)):
            assert is_market_open() is False

    def test_closed_on_saturday(self):
        with patch("feeds.market_data._now_et", return_value=_et(5, 10, 0)):
            assert is_market_open() is False

    def test_closed_on_sunday(self):
        with patch("feeds.market_data._now_et", return_value=_et(6, 12, 0)):
            assert is_market_open() is False


# ── init_db() ─────────────────────────────────────────────────────────────────


class TestInitDb:
    def test_creates_bars_table(self):
        conn = init_db(":memory:")
        result = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'bars'"
        ).fetchone()
        assert result is not None
        assert result[0] == "bars"
        conn.close()

    def test_bars_table_has_correct_columns(self):
        conn = init_db(":memory:")
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='bars' ORDER BY ordinal_position"
        ).fetchall()
        assert [c[0] for c in cols] == ["ticker", "timestamp", "open", "high", "low", "close", "volume"]
        conn.close()

    def test_idempotent_on_second_call(self, tmp_path):
        db = str(tmp_path / "test.duckdb")
        conn = init_db(db)
        conn.close()
        conn2 = init_db(db)
        conn2.close()

    def test_primary_key_rejects_exact_duplicate(self):
        conn = init_db(":memory:")
        df = _bars_df(n=1)
        store_bars(conn, df)
        # Inserting the exact same row again must not raise and must not add a row.
        store_bars(conn, df)
        count = conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        assert count == 1
        conn.close()


# ── store_bars() ──────────────────────────────────────────────────────────────


class TestStoreBars:
    def test_inserts_new_rows(self):
        conn = init_db(":memory:")
        df = _bars_df(tickers=["AAPL", "MSFT", "NVDA"])
        inserted = store_bars(conn, df)
        assert inserted == 3
        assert conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0] == 3
        conn.close()

    def test_skips_all_duplicates(self):
        conn = init_db(":memory:")
        df = _bars_df(n=2)
        store_bars(conn, df)
        inserted = store_bars(conn, df)
        assert inserted == 0
        conn.close()

    def test_empty_dataframe_returns_zero(self):
        conn = init_db(":memory:")
        empty = pd.DataFrame(
            columns=["ticker", "timestamp", "open", "high", "low", "close", "volume"]
        )
        assert store_bars(conn, empty) == 0
        conn.close()

    def test_partial_duplicate_inserts_only_new(self):
        conn = init_db(":memory:")
        df_first = _bars_df(n=2)
        store_bars(conn, df_first)

        # One brand-new row with a timestamp far in the past
        new_row = pd.DataFrame([{
            "ticker": "AAPL",
            "timestamp": datetime.datetime(2020, 1, 1, 15, 0, tzinfo=datetime.timezone.utc),
            "open": 300.0, "high": 301.0, "low": 299.0, "close": 300.5, "volume": 5000,
        }])
        combined = pd.concat([df_first, new_row], ignore_index=True)
        inserted = store_bars(conn, combined)
        assert inserted == 1
        conn.close()


# ── fetch_bars() ──────────────────────────────────────────────────────────────


class TestFetchBars:
    @patch("feeds.market_data._build_client")
    def test_returns_dataframe_with_correct_columns(self, mock_build):
        mock_build.return_value.get_stock_bars.return_value = _mock_alpaca_response("AAPL", 5)
        result = fetch_bars("AAPL", 5)
        assert result is not None
        assert list(result.columns) == ["ticker", "timestamp", "open", "high", "low", "close", "volume"]

    @patch("feeds.market_data._build_client")
    def test_ticker_column_has_correct_value(self, mock_build):
        mock_build.return_value.get_stock_bars.return_value = _mock_alpaca_response("MSFT", 3)
        result = fetch_bars("MSFT", 3)
        assert result is not None
        assert (result["ticker"] == "MSFT").all()

    @patch("feeds.market_data._build_client")
    def test_timestamps_are_utc(self, mock_build):
        mock_build.return_value.get_stock_bars.return_value = _mock_alpaca_response("AAPL", 2)
        result = fetch_bars("AAPL", 2)
        assert result is not None
        assert str(result["timestamp"].dt.tz) == "UTC"

    @patch("feeds.market_data._build_client")
    def test_returns_none_on_empty_response(self, mock_build):
        empty = MagicMock()
        empty.df = pd.DataFrame()
        mock_build.return_value.get_stock_bars.return_value = empty
        assert fetch_bars("AAPL", 5) is None

    @patch("feeds.market_data._build_client")
    def test_returns_none_on_api_exception(self, mock_build):
        mock_build.return_value.get_stock_bars.side_effect = ConnectionError("API down")
        result = fetch_bars("AAPL", 5)
        assert result is None  # must not raise
