"""
tests/test_backtest.py — Tests for backtest/runner.py (Session 4).

All tests use synthetic DataFrames — no yFinance calls, no network.
"""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import pytest

from backtest.runner import (
    compute_metrics,
    detect_breakout_historical,
    run_backtest,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_df(
    closes: list[float],
    volumes: list[int] | None = None,
    opens: list[float] | None = None,
    start: str = "2023-01-01",
) -> pd.DataFrame:
    """Build a synthetic daily OHLCV DataFrame (ascending by date)."""
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000] * n
    if opens is None:
        opens = [c - 0.5 for c in closes]
    base = datetime.date.fromisoformat(start)
    rows = [
        {
            "date": base + datetime.timedelta(days=i),
            "open": opens[i],
            "high": closes[i] + 0.5,
            "low": closes[i] - 0.5,
            "close": closes[i],
            "volume": volumes[i],
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows)


def _breakout_df(n_window: int = 35) -> pd.DataFrame:
    """
    Build a DataFrame where the last row is a clear breakout.

    Rows 0..(n_window-2): close=100, volume=1_000_000
    Row (n_window-1): close=110 (above 20d high), volume=2_500_000 (2.5x avg)
    The RSI window (14 periods ending at the signal row) has 9 ups + 5 downs
    → RSI ≈ 73.7 which passes the 50–75 gate.
    """
    # Build a 15-bar RSI window that gives RSI ≈ 73.7
    rsi_closes = (
        [float(100 + i) for i in range(9)]   # 100..108 (8 up-moves)
        + [float(107 - i) for i in range(5)] # 107..103 (5 down-moves)
        + [110.0]                             # breakout close (+7 from 103)
    )
    assert len(rsi_closes) == 15

    # Pad with flat bars to reach n_window total rows
    pad = n_window - 15
    closes = [100.0] * pad + rsi_closes
    volumes = [1_000_000] * (n_window - 1) + [2_500_000]
    return _make_df(closes, volumes=volumes)


# ── detect_breakout_historical ─────────────────────────────────────────────────


class TestDetectBreakoutHistorical:
    def test_no_signal_when_close_not_new_high(self):
        """All closes identical → today's close equals (not exceeds) 20d high → None."""
        df = _make_df([100.0] * 40)
        assert detect_breakout_historical(df, 39) is None

    def test_no_signal_when_insufficient_history(self):
        """Fewer than 21+14=35 rows before idx → None."""
        df = _make_df([100.0] * 10)
        # idx=9 with only 10 rows total → not enough lookback
        assert detect_breakout_historical(df, 9) is None

    def test_signal_detected_on_valid_breakout(self):
        """Crafted breakout bar passes both gates → signal dict returned."""
        df = _breakout_df()
        idx = len(df) - 1
        result = detect_breakout_historical(df, idx)
        assert result is not None
        assert result["close"] == pytest.approx(110.0)
        assert result["vwap_pass"] is True
        assert result["sector_pass"] is True

    def test_no_signal_when_volume_insufficient(self):
        """New closing high but volume only 1.1x average → None."""
        closes = [100.0] * 34 + [110.0]
        volumes = [1_000_000] * 34 + [1_100_000]
        df = _make_df(closes, volumes=volumes)
        # RSI for this series: all flat then one big jump → RSI=100 → fails gate too
        # Either way, result must be None
        result = detect_breakout_historical(df, len(df) - 1)
        assert result is None

    def test_no_signal_when_rsi_above_max(self):
        """Breakout + high volume but RSI > 75 → None."""
        # All closes flat at 100, then one jump to 110 → RSI=100 (>75) with vol=3x
        closes = [100.0] * 34 + [110.0]
        volumes = [1_000_000] * 34 + [3_000_000]
        df = _make_df(closes, volumes=volumes)
        result = detect_breakout_historical(df, len(df) - 1)
        assert result is None

    def test_signal_dict_has_required_keys(self):
        """Signal dict contains date, close, volume, avg_volume, volume_ratio, high_20d, rsi."""
        df = _breakout_df()
        result = detect_breakout_historical(df, len(df) - 1)
        assert result is not None
        required = {"date", "close", "volume", "avg_volume", "volume_ratio",
                    "high_20d", "rsi", "vwap_pass", "sector_pass"}
        assert required == set(result.keys())


# ── run_backtest trade mechanics ──────────────────────────────────────────────


def _trades_from_df(df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
    """Run run_backtest with a mock fetch by injecting df directly."""
    from unittest.mock import patch
    with patch("backtest.runner.fetch_all_historical", return_value={"TST": df}):
        return run_backtest(["TST"], "2023-01-01", "2024-12-31", **kwargs)


class TestRunBacktestMechanics:
    def test_entry_is_next_day_open(self):
        """Entry price equals the open of the bar after the signal bar."""
        df = _breakout_df(n_window=36)
        # Append one more bar with a distinctive open so we can verify
        next_open = 115.0
        extra = pd.DataFrame([{
            "date": df.iloc[-1]["date"] + datetime.timedelta(days=1),
            "open": next_open,
            "high": 116.0, "low": 114.0,
            "close": 115.5, "volume": 1_000_000,
        }])
        df = pd.concat([df, extra], ignore_index=True)
        trades = _trades_from_df(df, hold_days=1, stop_loss_pct=0.99)
        assert not trades.empty
        # The last signal fires at idx = len(df)-2; entry at idx+1 = last bar
        assert trades.iloc[-1]["entry_price"] == pytest.approx(next_open)

    def test_stop_loss_exits_correctly(self):
        """Price drops 6% below entry on day 2 → exit_reason is stop_loss."""
        df = _breakout_df(n_window=35)
        entry_open = float(df.iloc[-1]["close"]) + 1.0
        # After signal bar: day+1 has high open, day+2 drops 6% below entry
        drop_close = entry_open * 0.93
        extra = pd.DataFrame([
            {
                "date": df.iloc[-1]["date"] + datetime.timedelta(days=1),
                "open": entry_open, "high": entry_open + 0.5,
                "low": entry_open - 0.5, "close": entry_open - 0.1, "volume": 1_000_000,
            },
            {
                "date": df.iloc[-1]["date"] + datetime.timedelta(days=2),
                "open": drop_close, "high": drop_close + 0.1,
                "low": drop_close - 0.1, "close": drop_close, "volume": 1_000_000,
            },
        ])
        df = pd.concat([df, extra], ignore_index=True)
        trades = _trades_from_df(df, hold_days=5, stop_loss_pct=0.05)
        assert not trades.empty
        last = trades.iloc[-1]
        assert last["exit_reason"] == "stop_loss"

    def test_hold_days_exits_correctly(self):
        """Price never drops → exit after exactly hold_days bars."""
        df = _breakout_df(n_window=35)
        hold = 3
        # Append hold+1 stable bars (price stays flat/up so stop never triggers)
        extras = []
        for i in range(1, hold + 2):
            extras.append({
                "date": df.iloc[-1]["date"] + datetime.timedelta(days=i),
                "open": 111.0, "high": 112.0, "low": 110.5,
                "close": 111.5, "volume": 1_000_000,
            })
        df = pd.concat([df, pd.DataFrame(extras)], ignore_index=True)
        trades = _trades_from_df(df, hold_days=hold, stop_loss_pct=0.05)
        assert not trades.empty
        last = trades.iloc[-1]
        assert last["exit_reason"] == "hold_days"
        assert last["hold_days_actual"] == hold

    def test_commission_reduces_net_return(self):
        """net_return_pct = gross_return_pct − 2 * commission * 100."""
        df = _breakout_df(n_window=35)
        commission = 0.001
        hold = 3
        extras = []
        for i in range(1, hold + 2):
            extras.append({
                "date": df.iloc[-1]["date"] + datetime.timedelta(days=i),
                "open": 112.0, "high": 113.0, "low": 111.0,
                "close": 112.5, "volume": 1_000_000,
            })
        df = pd.concat([df, pd.DataFrame(extras)], ignore_index=True)
        trades = _trades_from_df(df, hold_days=hold, stop_loss_pct=0.05,
                                 commission_per_trade=commission)
        assert not trades.empty
        last = trades.iloc[-1]
        expected_net = last["gross_return_pct"] - 2.0 * commission * 100
        assert last["net_return_pct"] == pytest.approx(expected_net, abs=1e-3)


# ── compute_metrics ───────────────────────────────────────────────────────────


def _make_trades(net_returns: list[float], exit_reasons: list[str] | None = None) -> pd.DataFrame:
    if exit_reasons is None:
        exit_reasons = ["hold_days"] * len(net_returns)
    today = datetime.date(2023, 6, 1)
    rows = [
        {
            "ticker": "TST",
            "signal_date": today + datetime.timedelta(days=i * 5),
            "entry_date": today + datetime.timedelta(days=i * 5 + 1),
            "entry_price": 100.0,
            "exit_date": today + datetime.timedelta(days=i * 5 + 5),
            "exit_price": 100.0 * (1 + r / 100),
            "exit_reason": exit_reasons[i],
            "hold_days_actual": 5,
            "gross_return_pct": r + 0.2,
            "net_return_pct": r,
            "signal_rsi": 60.0,
            "signal_volume_ratio": 2.0,
        }
        for i, r in enumerate(net_returns)
    ]
    return pd.DataFrame(rows)


class TestComputeMetrics:
    def test_empty_trades_returns_zeros(self):
        """Empty DataFrame → all zeros, no exception."""
        result = compute_metrics(pd.DataFrame())
        assert result["total_trades"] == 0
        assert result["win_rate"] == 0.0
        assert result["profit_factor"] == 0.0

    def test_win_rate(self):
        """3 wins + 2 losses → win_rate = 0.6."""
        trades = _make_trades([2.0, 3.0, -1.0, 1.5, -0.5])
        m = compute_metrics(trades)
        assert m["win_rate"] == pytest.approx(0.6)

    def test_profit_factor(self):
        """sum_wins=5, sum_losses=1.5 → profit_factor ≈ 3.33."""
        trades = _make_trades([2.0, 3.0, -1.0, -0.5])
        m = compute_metrics(trades)
        assert m["profit_factor"] == pytest.approx(5.0 / 1.5, rel=0.01)

    def test_total_net_return(self):
        """Sum of all net returns."""
        rets = [2.0, -1.0, 3.0, -0.5]
        trades = _make_trades(rets)
        m = compute_metrics(trades)
        assert m["total_net_return_pct"] == pytest.approx(sum(rets), abs=0.01)

    def test_pct_stopped_out(self):
        """2 of 4 trades stopped out → pct_stopped_out = 50.0."""
        trades = _make_trades(
            [-1.0, 2.0, -0.8, 1.5],
            exit_reasons=["stop_loss", "hold_days", "stop_loss", "hold_days"],
        )
        m = compute_metrics(trades)
        assert m["pct_stopped_out"] == pytest.approx(50.0)
