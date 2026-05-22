"""
backtest/structure_runner.py — Session 5: backtest of the structure-based breakout.

Uses detect_structure_breakout (6 gates: trend + BOS + volume + candle + RSI + MACD)
instead of the Session 4c 20-day close breakout. Compares against 4c baseline.

Reuses fetch_all_historical, compute_atr, fetch_earnings_dates, is_near_earnings,
and compute_metrics from backtest.runner.

Returns:
    run_structure_backtest, main.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

import config
from backtest.runner import (
    compute_atr,
    compute_metrics,
    fetch_all_historical,
    fetch_earnings_dates,
    is_near_earnings,
)
from journal.logger import get_logger
from signals.structure import detect_structure_breakout

logger = get_logger(__name__)

# Hardcoded Session 4c results — in-sample (2023-2024) and OOS (2025)
_4C_IS: dict[str, Any] = {
    "total_trades": 164,
    "win_rate": 0.561,
    "avg_win_pct": 3.5673,
    "avg_loss_pct": -3.4626,
    "profit_factor": 1.3164,
    "max_drawdown_pct": -60.71,
    "sharpe_ratio": 1.6017,
    "total_net_return_pct": 78.88,
}

_4C_OOS: dict[str, Any] = {
    "total_trades": 65,
    "win_rate": 0.4923,
    "avg_win_pct": 3.6892,
    "avg_loss_pct": -3.1029,
    "profit_factor": 1.1529,
    "max_drawdown_pct": -26.74,
    "sharpe_ratio": 0.7792,
    "total_net_return_pct": 15.66,
}

# Minimum bars for EMA(200) + buffer
_MIN_HISTORY: int = 205


def run_structure_backtest(
    tickers: list[str],
    start: str,
    end: str,
    hold_days: int = 5,
    stop_loss_pct: float = 0.05,
    commission_per_trade: float = 0.001,
    atr_multiplier: float = 2.0,
    earnings_window_days: int = 5,
) -> pd.DataFrame:
    """
    Run the structure-breakout backtest across all tickers for the given date range.

    Entry: next day open after signal fires.
    Stop:  ATR(14) x atr_multiplier.
    Invalidation: close drops below swing_high_level → exit next open.
    Hold:  max hold_days bars before time exit.
    Skip:  signals within earnings_window_days of an earnings date.

    Returns:
        DataFrame of trades. attrs["signals_skipped_earnings"] = count.
    """
    all_data = fetch_all_historical(tickers, start, end)
    trades: list[dict[str, Any]] = []
    skipped_earnings = 0

    for ticker, df in all_data.items():
        if df is None or len(df) < _MIN_HISTORY:
            logger.debug("Skipping %s: insufficient data (%s bars)", ticker,
                         0 if df is None else len(df))
            continue

        earnings = fetch_earnings_dates(ticker, start, end)
        n = len(df)

        for idx in range(200, n - 1):
            signal = detect_structure_breakout(df, idx, ticker=ticker)
            if signal is None:
                continue

            if is_near_earnings(signal["date"], earnings, window_days=earnings_window_days):
                skipped_earnings += 1
                continue

            entry_idx = idx + 1
            entry_price = float(df.iloc[entry_idx]["open"])
            if entry_price <= 0:
                continue

            atr = compute_atr(df, entry_idx, period=config.BACKTEST_ATR_PERIOD)
            if atr is None:
                continue

            stop_price = entry_price - atr_multiplier * atr
            stop_pct_implied = (entry_price - stop_price) / entry_price
            swing_high_level = signal["swing_high_level"]

            exit_idx = entry_idx
            exit_price = entry_price
            exit_reason = "hold_days"
            prev_close = float(df.iloc[entry_idx]["close"])

            for j in range(1, hold_days + 1):
                bar_idx = entry_idx + j
                if bar_idx >= n:
                    exit_idx = n - 1
                    exit_price = float(df.iloc[exit_idx]["close"])
                    exit_reason = "end_of_data"
                    break
                bar_open = float(df.iloc[bar_idx]["open"])
                bar_close = float(df.iloc[bar_idx]["close"])
                # Priority 1: gap-down through stop at open
                if bar_open <= stop_price:
                    exit_idx = bar_idx
                    exit_price = bar_open
                    exit_reason = "stop_loss"
                    break
                # Priority 2: prior close fell back below swing high (thesis dead)
                if prev_close < swing_high_level:
                    exit_idx = bar_idx
                    exit_price = bar_open
                    exit_reason = "invalidation"
                    break
                # Priority 3: intraday close through stop
                if bar_close <= stop_price:
                    exit_idx = bar_idx
                    exit_price = bar_close
                    exit_reason = "stop_loss"
                    break
                # Priority 4: time exit
                if j == hold_days:
                    exit_idx = bar_idx
                    exit_price = bar_close
                    exit_reason = "hold_days"
                    break
                prev_close = bar_close

            gross = (exit_price - entry_price) / entry_price
            net = gross - 2.0 * commission_per_trade
            hold_actual = exit_idx - entry_idx

            trades.append({
                "ticker": ticker,
                "signal_date": signal["date"],
                "entry_date": df.iloc[entry_idx]["date"],
                "entry_price": entry_price,
                "exit_date": df.iloc[exit_idx]["date"],
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "hold_days_actual": hold_actual,
                "gross_return_pct": round(gross * 100, 4),
                "net_return_pct": round(net * 100, 4),
                "signal_rsi": signal["rsi_14"],
                "signal_volume_ratio": round(signal["volume_ratio"], 4),
                "atr_at_entry": atr,
                "stop_price": round(stop_price, 4),
                "stop_pct_implied": round(stop_pct_implied * 100, 4),
                "swing_high_level": round(swing_high_level, 4),
                "ema_50": signal["ema_50"],
                "ema_200": signal["ema_200"],
            })

    result = pd.DataFrame(trades)
    result.attrs["signals_skipped_earnings"] = skipped_earnings
    return result


# ── Verdict helpers ───────────────────────────────────────────────────────────


def _verdict_s5_is(m: dict[str, Any]) -> tuple[bool, list[str]]:
    """Session 5 must beat 4c on at least 3 of 4 metrics to justify replacing it."""
    beats = [
        (m["win_rate"] > _4C_IS["win_rate"],
         f"win_rate {m['win_rate']:.4f} vs 4c {_4C_IS['win_rate']}"),
        (m["profit_factor"] > _4C_IS["profit_factor"],
         f"profit_factor {m['profit_factor']:.4f} vs 4c {_4C_IS['profit_factor']}"),
        (m["avg_win_pct"] > abs(m["avg_loss_pct"]),
         f"avg_win {m['avg_win_pct']:.4f}% vs |avg_loss| {abs(m['avg_loss_pct']):.4f}%"),
        (m["sharpe_ratio"] > _4C_IS["sharpe_ratio"],
         f"sharpe {m['sharpe_ratio']:.4f} vs 4c {_4C_IS['sharpe_ratio']}"),
    ]
    n_beats = sum(1 for passed, _ in beats if passed)
    failures = [msg for passed, msg in beats if not passed]
    return n_beats >= 3, failures


def _verdict_s5_oos(m: dict[str, Any]) -> tuple[bool, list[str]]:
    """OOS minimum thresholds — must show positive expected value on unseen data."""
    criteria = [
        (m["total_trades"] >= 15,
         f"total_trades={m['total_trades']} (need >=15)"),
        (m["profit_factor"] >= 1.1,
         f"profit_factor={m['profit_factor']:.4f} (need >=1.1)"),
        (m["win_rate"] >= 0.50,
         f"win_rate={m['win_rate']:.4f} (need >=0.50)"),
        (m["total_net_return_pct"] > 0,
         f"total_net_return_pct={m['total_net_return_pct']:.4f}% (need >0)"),
    ]
    failures = [msg for passed, msg in criteria if not passed]
    return len(failures) == 0, failures


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """
    Run Session 5 in-sample (2023-2024) and OOS (2025).
    Print 4-column comparison against hardcoded 4c baseline.

    NOTE: VWAP and sector filters are active in the live scanner only.
    """
    print("=" * 80)
    print("SIGNAL BRAIN — SESSION 5: STRUCTURE BREAKOUT vs SESSION 4c BASELINE")
    print("Gates  : Trend (EMA 50/200) + BOS (swing high) + Volume + Candle + RSI(14) + MACD")
    print("Stop   : ATR(14) × 2.0  |  Invalidation: close < swing_high_level")
    print("Period : 2023-2024 (in-sample)  |  2025 (OOS — unseen, parameters frozen)")
    print("NOTE   : VWAP and sector filters are active in live scanner only.")
    print("=" * 80)
    print(f"Scanning {len(config.ALL_TICKERS)} tickers …\n")

    common_kwargs: dict[str, Any] = dict(
        hold_days=config.BACKTEST_HOLD_DAYS,
        stop_loss_pct=config.BACKTEST_STOP_LOSS_PCT,
        commission_per_trade=config.BACKTEST_COMMISSION,
        atr_multiplier=config.BACKTEST_ATR_MULTIPLIER,
        earnings_window_days=config.EARNINGS_WINDOW_DAYS,
    )

    trades_is = run_structure_backtest(
        tickers=config.ALL_TICKERS,
        start=config.BACKTEST_START,
        end=config.BACKTEST_END,
        **common_kwargs,
    )
    trades_oos = run_structure_backtest(
        tickers=config.ALL_TICKERS,
        start=config.OOS_START,
        end=config.OOS_END,
        **common_kwargs,
    )

    m_is = compute_metrics(trades_is)
    m_oos = compute_metrics(trades_oos)

    W = 13
    print("=" * 80)
    print("SESSION 4c BASELINE vs SESSION 5: STRUCTURE BREAKOUT")
    print("=" * 80)
    header = (
        f"{'Metric':<30}"
        f" {'4c IN-SAMPLE':>{W}}"
        f" {'5 IN-SAMPLE':>{W}}"
        f" {'4c OOS 2025':>{W}}"
        f" {'5 OOS 2025':>{W}}"
    )
    print(header)
    print("─" * 80)

    def _r(label: str, c_is: Any, s_is: Any, c_oos: Any, s_oos: Any) -> None:
        print(
            f"  {label:<28}"
            f" {str(c_is):>{W}}"
            f" {str(s_is):>{W}}"
            f" {str(c_oos):>{W}}"
            f" {str(s_oos):>{W}}"
        )

    _r("total_trades",
       _4C_IS["total_trades"], m_is["total_trades"],
       _4C_OOS["total_trades"], m_oos["total_trades"])
    _r("win_rate",
       _4C_IS["win_rate"], m_is["win_rate"],
       _4C_OOS["win_rate"], m_oos["win_rate"])
    _r("avg_win_pct",
       _4C_IS["avg_win_pct"], m_is["avg_win_pct"],
       _4C_OOS["avg_win_pct"], m_oos["avg_win_pct"])
    _r("avg_loss_pct",
       _4C_IS["avg_loss_pct"], m_is["avg_loss_pct"],
       _4C_OOS["avg_loss_pct"], m_oos["avg_loss_pct"])
    _r("profit_factor",
       _4C_IS["profit_factor"], m_is["profit_factor"],
       _4C_OOS["profit_factor"], m_oos["profit_factor"])
    _r("max_drawdown_pct",
       _4C_IS["max_drawdown_pct"], m_is["max_drawdown_pct"],
       _4C_OOS["max_drawdown_pct"], m_oos["max_drawdown_pct"])
    _r("sharpe_ratio",
       _4C_IS["sharpe_ratio"], m_is["sharpe_ratio"],
       _4C_OOS["sharpe_ratio"], m_oos["sharpe_ratio"])
    _r("total_net_return_pct",
       _4C_IS["total_net_return_pct"], m_is["total_net_return_pct"],
       _4C_OOS["total_net_return_pct"], m_oos["total_net_return_pct"])

    print()
    passed_is, failures_is = _verdict_s5_is(m_is)
    passed_oos, failures_oos = _verdict_s5_oos(m_oos)
    print(f"  SESSION 5 IN-SAMPLE VERDICT  : {'PASS ✓' if passed_is else 'FAIL ✗'}")
    for f in failures_is:
        print(f"    • {f}")
    print(f"  SESSION 5 OOS VERDICT        : {'PASS ✓' if passed_oos else 'FAIL ✗'}")
    for f in failures_oos:
        print(f"    • {f}")

    print()
    if passed_is and passed_oos:
        print("  DECISION: Structure breakout REPLACES 4c as primary signal.")
        print("            Build Sessions 6-8 on structure_breakout.")
    elif passed_oos:
        print("  DECISION: Run BOTH signals in parallel during paper trading.")
        print("            Log which performs better on live data.")
    else:
        print("  DECISION: Keep 4c as primary. Structure breakout = additive filter only.")
    print("=" * 80)

    if not trades_is.empty:
        cols = ["ticker", "signal_date", "entry_price", "exit_price",
                "net_return_pct", "exit_reason", "swing_high_level"]
        print("\n── TOP 5 BEST (Session 5 in-sample) ──")
        print(trades_is.nlargest(5, "net_return_pct")[cols].to_string(index=False))
        print("\n── TOP 5 WORST (Session 5 in-sample) ──")
        print(trades_is.nsmallest(5, "net_return_pct")[cols].to_string(index=False))

    if not trades_oos.empty:
        print("\n── OOS 2025 ALL TRADES ──")
        print(trades_oos[cols].to_string(index=False))


if __name__ == "__main__":
    main()
