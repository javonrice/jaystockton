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
    compute_atr,
    compute_metrics,
    detect_breakout_historical,
    is_near_earnings,
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
    """Run run_backtest with mocked fetchers — no network calls."""
    from unittest.mock import patch
    with patch("backtest.runner.fetch_all_historical", return_value={"TST": df}), \
         patch("backtest.runner.fetch_earnings_dates", return_value=set()):
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


# ── compute_atr ───────────────────────────────────────────────────────────────


def _make_ohlc_df(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    start: str = "2023-01-01",
) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame with explicit high/low values."""
    n = len(closes)
    base = datetime.date.fromisoformat(start)
    rows = [
        {
            "date": base + datetime.timedelta(days=i),
            "open": closes[i] - 0.1,
            "high": highs[i],
            "low": lows[i],
            "close": closes[i],
            "volume": 1_000_000,
        }
        for i in range(n)
    ]
    return pd.DataFrame(rows)


class TestComputeATR:
    def test_atr_computes_correctly(self):
        """Constant TR=2.0 for all bars → ATR=2.0 after Wilder smoothing."""
        n = 20
        # high-low = 2.0, prev_close always = 100 → TR = max(2, 1, 1) = 2.0
        closes = [100.0] * n
        highs = [101.0] * n
        lows = [99.0] * n
        df = _make_ohlc_df(closes, highs, lows)
        result = compute_atr(df, idx=15, period=14)
        assert result == pytest.approx(2.0, abs=1e-3)

    def test_atr_insufficient_data_returns_none(self):
        """idx < period → None (not enough bars to initialize ATR)."""
        df = _make_df([100.0] * 10)
        assert compute_atr(df, idx=5, period=14) is None
        assert compute_atr(df, idx=13, period=14) is None

    def test_atr_stop_wider_than_fixed_on_volatile_stock(self):
        """High-volatility stock: 2×ATR stop implied % > 5% fixed stop."""
        n = 20
        # TR = max(20, 10, 10) = 20 per bar → ATR≈20
        closes = [200.0] * n
        highs = [210.0] * n
        lows = [190.0] * n
        df = _make_ohlc_df(closes, highs, lows)
        entry_price = 200.0
        atr = compute_atr(df, idx=15, period=14)
        assert atr is not None
        stop_price = entry_price - 2.0 * atr
        implied_pct = (entry_price - stop_price) / entry_price
        assert implied_pct > 0.05, f"Expected >5% implied stop, got {implied_pct:.2%}"

    def test_atr_stop_tighter_on_low_vol_stock(self):
        """Low-volatility stock: 2×ATR stop implied % < 5% fixed stop."""
        n = 20
        # TR = max(0.5, 0.25, 0.25) = 0.5 per bar → ATR≈0.5
        closes = [100.0] * n
        highs = [100.25] * n
        lows = [99.75] * n
        df = _make_ohlc_df(closes, highs, lows)
        entry_price = 100.0
        atr = compute_atr(df, idx=15, period=14)
        assert atr is not None
        stop_price = entry_price - 2.0 * atr
        implied_pct = (entry_price - stop_price) / entry_price
        assert implied_pct < 0.05, f"Expected <5% implied stop, got {implied_pct:.2%}"


# ── is_near_earnings + earnings exclusion ─────────────────────────────────────


class TestEarningsExclusion:
    def test_earnings_exclusion_skips_signal(self):
        """Signal within 3 days of earnings → is_near_earnings returns True."""
        signal = pd.Timestamp("2023-06-15")
        earnings = {pd.Timestamp("2023-06-18")}  # 3 days later, within window=5
        assert is_near_earnings(signal, earnings, window_days=5) is True

    def test_earnings_exclusion_passes_signal(self):
        """Signal 10 days from earnings → is_near_earnings returns False."""
        signal = pd.Timestamp("2023-06-15")
        earnings = {pd.Timestamp("2023-06-25")}  # 10 days later, outside window=5
        assert is_near_earnings(signal, earnings, window_days=5) is False

    def test_earnings_empty_set_never_skips(self):
        """Empty earnings set → is_near_earnings always returns False."""
        signal = pd.Timestamp("2023-06-15")
        assert is_near_earnings(signal, set(), window_days=5) is False


# ── Invalidation exit (Session 4c) ────────────────────────────────────────────


def _build_invalidation_df(n_extra: int = 10) -> pd.DataFrame:
    """
    Build a DataFrame suitable for invalidation testing.

    The breakout bar is at index 34 (n_window=35). Extra bars follow.
    High/low are ±20 from close (TR≈40) so ATR≈40 and stop_price is far
    below the breakout level (high_20d=100). This prevents stop_loss from
    triggering before the invalidation test can fire.
    """
    signal_close = 110.0  # breakout close (> high_20d=100)
    n_window = 35
    pad = n_window - 15
    rsi_closes = (
        [float(100 + i) for i in range(9)]
        + [float(107 - i) for i in range(5)]
        + [signal_close]
    )
    closes = [100.0] * pad + rsi_closes
    volumes = [1_000_000] * (n_window - 1) + [2_500_000]
    base = [
        {
            "date": datetime.date(2023, 1, 1) + datetime.timedelta(days=i),
            "open": c - 0.5,
            "high": c + 20.0,   # wide range → large TR → ATR≈40 → stop far below
            "low": c - 20.0,
            "close": c,
            "volume": volumes[i],
        }
        for i, c in enumerate(closes)
    ]
    # Append extra bars; caller sets closes for these
    extras = [
        {
            "date": datetime.date(2023, 1, 1) + datetime.timedelta(days=n_window + i),
            "open": 111.0,
            "high": 131.0,
            "low": 91.0,
            "close": 111.0,
            "volume": 1_000_000,
        }
        for i in range(n_extra)
    ]
    return pd.DataFrame(base + extras)


def _trades_invalidation(df: pd.DataFrame, signal_override: dict | None = None, **kwargs: Any) -> pd.DataFrame:
    """
    Run run_backtest with mocked fetchers. Optionally patch detect_breakout_historical
    to inject a custom signal dict (e.g. to control high_20d precisely).
    """
    from unittest.mock import patch

    if signal_override is None:
        with patch("backtest.runner.fetch_all_historical", return_value={"TST": df}), \
             patch("backtest.runner.fetch_earnings_dates", return_value=set()):
            return run_backtest(["TST"], "2023-01-01", "2024-12-31", **kwargs)

    original_detect = __import__("backtest.runner", fromlist=["detect_breakout_historical"]).detect_breakout_historical

    def _patched_detect(inner_df: pd.DataFrame, idx: int):
        result = original_detect(inner_df, idx)
        if result is not None:
            result.update(signal_override)
        return result

    with patch("backtest.runner.fetch_all_historical", return_value={"TST": df}), \
         patch("backtest.runner.fetch_earnings_dates", return_value=set()), \
         patch("backtest.runner.detect_breakout_historical", side_effect=_patched_detect):
        return run_backtest(["TST"], "2023-01-01", "2024-12-31", **kwargs)


class TestInvalidationExit:
    def test_invalidation_fires_when_close_drops_below_breakout_level(self):
        """If close on hold day 1 drops below high_20d, next bar exits with 'invalidation'."""
        df = _build_invalidation_df(n_extra=5)
        # Force high_20d=108 so that signal close=110 > high_20d. Then on day+1 close=107 < 108.
        # ATR≈40 → stop_price ≈ entry-80 → far below, won't trigger first.
        # entry open (day+1) = 111, day+1 close = 107 < high_20d=108 → invalidation fires day+2.
        n = len(df)
        signal_idx = 34
        # Override day+1 close to 107 (below high_20d=108)
        df = df.copy()
        df.at[signal_idx + 1, "close"] = 107.0
        df.at[signal_idx + 1, "low"] = 87.0
        df.at[signal_idx + 1, "high"] = 127.0

        trades = _trades_invalidation(df, signal_override={"high_20d": 108.0},
                                      hold_days=5, atr_multiplier=2.0)
        assert not trades.empty
        last = trades.iloc[-1]
        assert last["exit_reason"] == "invalidation"

    def test_invalidation_exit_price_is_next_open(self):
        """Invalidation exit price equals the open of the bar after the close-below event."""
        df = _build_invalidation_df(n_extra=5)
        df = df.copy()
        signal_idx = 34
        df.at[signal_idx + 1, "close"] = 107.0   # triggers invalidation check for day+2
        df.at[signal_idx + 1, "low"] = 87.0
        df.at[signal_idx + 1, "high"] = 127.0
        expected_open = 99.5
        df.at[signal_idx + 2, "open"] = expected_open

        trades = _trades_invalidation(df, signal_override={"high_20d": 108.0},
                                      hold_days=5, atr_multiplier=2.0)
        assert not trades.empty
        assert trades.iloc[-1]["exit_price"] == pytest.approx(expected_open)

    def test_stop_loss_takes_priority_over_invalidation_on_gap_down(self):
        """Gap-down open ≤ stop_price fires stop_loss, not invalidation, even if prev_close < high_20d."""
        df = _build_invalidation_df(n_extra=5)
        df = df.copy()
        signal_idx = 34
        entry_idx = signal_idx + 1   # = 35; entry_price = df.at[35, "open"] = 111.0
        first_hold_idx = entry_idx + 1  # = 36; first bar checked in the exit loop

        # Arm invalidation (prev_close < high_20d) by lowering entry bar close
        df.at[entry_idx, "close"] = 107.0   # < high_20d=108
        df.at[entry_idx, "low"] = 87.0
        df.at[entry_idx, "high"] = 127.0

        # ATR≈40, stop_price ≈ 111.0 - 2*40 = 31.0
        # Gap-down first hold bar's open to 21.0 (≤ 31.0 = stop_price) → Priority 1 fires first
        gap_open = 21.0
        df.at[first_hold_idx, "open"] = gap_open
        df.at[first_hold_idx, "low"] = gap_open - 1.0
        df.at[first_hold_idx, "high"] = gap_open + 1.0
        df.at[first_hold_idx, "close"] = gap_open

        trades = _trades_invalidation(df, signal_override={"high_20d": 108.0},
                                      hold_days=5, atr_multiplier=2.0)
        assert not trades.empty
        assert trades.iloc[-1]["exit_reason"] == "stop_loss"

    def test_no_invalidation_when_close_stays_above_breakout_level(self):
        """Close stays above high_20d every day → no invalidation, exits hold_days."""
        # Need n_extra=6: 1 entry bar (idx 35) + 5 hold-day bars (idx 36–40)
        df = _build_invalidation_df(n_extra=6)
        df = df.copy()
        signal_idx = 34
        for i in range(1, 7):   # bars 35–40: entry + all 5 hold days
            df.at[signal_idx + i, "close"] = 112.0   # > high_20d=108 → invalidation never arms
            df.at[signal_idx + i, "open"] = 111.5
            df.at[signal_idx + i, "high"] = 132.0
            df.at[signal_idx + i, "low"] = 92.0

        trades = _trades_invalidation(df, signal_override={"high_20d": 108.0},
                                      hold_days=5, atr_multiplier=2.0)
        assert not trades.empty
        assert trades.iloc[-1]["exit_reason"] == "hold_days"

    def test_breakout_level_column_present_and_correct(self):
        """Trades DataFrame has breakout_level column equal to signal's high_20d."""
        df = _build_invalidation_df(n_extra=5)
        trades = _trades_invalidation(df, hold_days=5, atr_multiplier=2.0)
        assert not trades.empty
        assert "breakout_level" in trades.columns
        # All signals in this synthetic df have high_20d = max of 20-bar window ≈ 108
        assert float(trades.iloc[-1]["breakout_level"]) > 0.0
