"""
backtest/runner.py — Session 4: historical backtest of the two-gate signal.

Applies the breakout + RSI gates (Sessions 2+3) to 2+ years of yFinance
daily data. VWAP and sector gates are excluded — minute bars are not
available on the free tier, and sector ETF alignment adds complexity that
is better addressed once the core signal shows edge.

NOTE: Backtest applies breakout + RSI gates only.
      VWAP and sector filters are active in the live scanner.

Requires:
    yfinance>=0.2.40

Returns:
    fetch_historical_data, fetch_all_historical, detect_breakout_historical,
    run_backtest, compute_metrics, main.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf

import config
from journal.logger import get_logger

logger = get_logger(__name__)

# RSI period constants (must match Session 3 values)
_RSI_PERIOD: int = 14
_RSI_MIN: float = 50.0
_RSI_MAX: float = 75.0
_VOLUME_RATIO_MIN: float = 1.5
_LOOKBACK: int = 20


# ── RSI (self-contained copy — keeps backtest independent of live signals) ────


def _compute_rsi(closes: list[float], period: int) -> Optional[float]:
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


# ── Data fetching ─────────────────────────────────────────────────────────────


def fetch_historical_data(ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """
    Fetch daily OHLCV from yFinance for the given date range.

    Args:
        ticker: Stock symbol.
        start: Start date 'YYYY-MM-DD' (inclusive).
        end: End date 'YYYY-MM-DD' (inclusive).

    Returns:
        DataFrame with columns [date, open, high, low, close, volume], or None on error.
    """
    try:
        raw = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            multi_level_index=False,
        )
        if raw is None or raw.empty:
            logger.warning("No data returned for %s", ticker)
            return None
        raw = raw.reset_index()
        raw.columns = [c.lower() for c in raw.columns]
        raw = raw.rename(columns={"date": "date"})
        raw["date"] = pd.to_datetime(raw["date"]).dt.date
        df = raw[["date", "open", "high", "low", "close", "volume"]].copy()
        df = df.dropna(subset=["close", "volume"])
        df = df.sort_values("date").reset_index(drop=True)
        return df
    except Exception as exc:
        logger.error("fetch_historical_data failed for %s: %s", ticker, exc)
        return None


def fetch_all_historical(
    tickers: list[str], start: str, end: str
) -> dict[str, Optional[pd.DataFrame]]:
    """
    Fetch historical data for each ticker independently.

    Args:
        tickers: List of stock symbols.
        start: Start date 'YYYY-MM-DD'.
        end: End date 'YYYY-MM-DD'.

    Returns:
        Dict mapping ticker → DataFrame (or None if fetch failed).
    """
    results: dict[str, Optional[pd.DataFrame]] = {}
    for ticker in tickers:
        results[ticker] = fetch_historical_data(ticker, start, end)
    return results


# ── Signal detection on historical slice ─────────────────────────────────────


def detect_breakout_historical(df: pd.DataFrame, idx: int) -> Optional[dict[str, Any]]:
    """
    Apply the two-gate (breakout + RSI) signal logic to row idx of df.

    No look-ahead: only rows 0..idx are used. idx is 'today'; idx-1..idx-20
    are the lookback window. VWAP and sector gates are marked True (not applicable).

    Args:
        df: Full historical DataFrame sorted ascending by date.
        idx: Index of the row to evaluate as today.

    Returns:
        Signal dict or None.
    """
    if idx < _LOOKBACK + _RSI_PERIOD:
        return None

    window = df.iloc[idx - _LOOKBACK : idx]
    today = df.iloc[idx]

    high_20d = float(window["close"].max())
    avg_vol = float(window["volume"].mean())
    today_close = float(today["close"])
    today_vol = float(today["volume"])

    if today_close <= high_20d:
        return None

    vol_ratio = today_vol / avg_vol if avg_vol > 0 else 0.0
    if vol_ratio < _VOLUME_RATIO_MIN:
        return None

    # RSI gate — use close[idx-14:idx+1] (15 values = 14 periods)
    rsi_closes = df["close"].iloc[idx - _RSI_PERIOD : idx + 1].tolist()
    rsi_val = _compute_rsi(rsi_closes, _RSI_PERIOD)
    if rsi_val is None or not (_RSI_MIN <= rsi_val <= _RSI_MAX):
        return None

    return {
        "date": today["date"],
        "close": today_close,
        "volume": today_vol,
        "avg_volume": avg_vol,
        "volume_ratio": vol_ratio,
        "high_20d": high_20d,
        "rsi": rsi_val,
        "vwap_pass": True,    # not evaluated in backtest
        "sector_pass": True,  # not evaluated in backtest
    }


# ── Backtest loop ─────────────────────────────────────────────────────────────


def run_backtest(
    tickers: list[str],
    start: str,
    end: str,
    hold_days: int = 5,
    stop_loss_pct: float = 0.05,
    commission_per_trade: float = 0.001,
) -> pd.DataFrame:
    """
    Run the full backtest across all tickers for the given date range.

    Entry is next day's open after signal fires. Exit is the earlier of:
      - hold_days trading days after entry
      - stop triggered when close falls stop_loss_pct below entry price

    Args:
        tickers: List of symbols to scan.
        start: Start date 'YYYY-MM-DD'.
        end: End date 'YYYY-MM-DD'.
        hold_days: Maximum bars to hold.
        stop_loss_pct: Stop loss as fraction (0.05 = 5%).
        commission_per_trade: One-way commission fraction; round-trip = 2x.

    Returns:
        DataFrame of all trades with performance columns.
    """
    all_data = fetch_all_historical(tickers, start, end)
    trades: list[dict[str, Any]] = []

    for ticker, df in all_data.items():
        if df is None or len(df) < 30:
            logger.debug("Skipping %s: insufficient data", ticker)
            continue

        n = len(df)
        for idx in range(_LOOKBACK + _RSI_PERIOD, n - 1):
            signal = detect_breakout_historical(df, idx)
            if signal is None:
                continue

            entry_idx = idx + 1
            entry_price = float(df.iloc[entry_idx]["open"])
            if entry_price <= 0:
                continue

            stop_price = entry_price * (1.0 - stop_loss_pct)
            exit_idx = entry_idx
            exit_price = entry_price
            exit_reason = "hold_days"

            for j in range(1, hold_days + 1):
                bar_idx = entry_idx + j
                if bar_idx >= n:
                    exit_idx = n - 1
                    exit_price = float(df.iloc[exit_idx]["close"])
                    exit_reason = "end_of_data"
                    break
                bar_close = float(df.iloc[bar_idx]["close"])
                if bar_close <= stop_price:
                    exit_idx = bar_idx
                    exit_price = bar_close
                    exit_reason = "stop_loss"
                    break
                if j == hold_days:
                    exit_idx = bar_idx
                    exit_price = bar_close
                    exit_reason = "hold_days"

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
                "signal_rsi": signal["rsi"],
                "signal_volume_ratio": round(signal["volume_ratio"], 4),
            })

    return pd.DataFrame(trades)


# ── Performance metrics ───────────────────────────────────────────────────────


def compute_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    """
    Compute the full performance report from a trades DataFrame.

    Args:
        trades: Output of run_backtest().

    Returns:
        Dict of performance metrics.
    """
    zeros: dict[str, Any] = {
        "total_trades": 0,
        "win_rate": 0.0,
        "avg_win_pct": 0.0,
        "avg_loss_pct": 0.0,
        "avg_net_return_pct": 0.0,
        "profit_factor": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe_ratio": 0.0,
        "total_net_return_pct": 0.0,
        "best_trade_pct": 0.0,
        "worst_trade_pct": 0.0,
        "avg_hold_days": 0.0,
        "signals_per_month": 0.0,
        "pct_stopped_out": 0.0,
    }
    if trades.empty:
        return zeros

    rets = trades["net_return_pct"]
    wins = rets[rets > 0]
    losses = rets[rets <= 0]

    sum_wins = wins.sum()
    sum_losses = abs(losses.sum())
    profit_factor = (sum_wins / sum_losses) if sum_losses > 0 else float("inf")

    # Max drawdown on cumulative sum of returns
    cum = rets.cumsum()
    peak = cum.cummax()
    drawdown = (cum - peak)
    max_dd = float(drawdown.min())

    # Sharpe: annualized (252 trading days), risk-free = 0
    mean_ret = rets.mean()
    std_ret = rets.std(ddof=1)
    sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0

    # Signals per month: approximate from date range
    if len(trades) >= 2:
        first = pd.to_datetime(trades["signal_date"].min())
        last = pd.to_datetime(trades["signal_date"].max())
        months = max((last - first).days / 30.44, 1.0)
        signals_per_month = len(trades) / months
    else:
        signals_per_month = float(len(trades))

    pct_stopped = (
        100.0 * (trades["exit_reason"] == "stop_loss").sum() / len(trades)
    )

    return {
        "total_trades": int(len(trades)),
        "win_rate": round(float(len(wins) / len(trades)), 4),
        "avg_win_pct": round(float(wins.mean()) if len(wins) else 0.0, 4),
        "avg_loss_pct": round(float(losses.mean()) if len(losses) else 0.0, 4),
        "avg_net_return_pct": round(float(mean_ret), 4),
        "profit_factor": round(profit_factor, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "sharpe_ratio": round(sharpe, 4),
        "total_net_return_pct": round(float(rets.sum()), 4),
        "best_trade_pct": round(float(rets.max()), 4),
        "worst_trade_pct": round(float(rets.min()), 4),
        "avg_hold_days": round(float(trades["hold_days_actual"].mean()), 2),
        "signals_per_month": round(signals_per_month, 2),
        "pct_stopped_out": round(pct_stopped, 2),
    }


# ── PASS/FAIL verdict ─────────────────────────────────────────────────────────


def _verdict(m: dict[str, Any]) -> tuple[bool, list[str]]:
    criteria = [
        (m["total_trades"] >= 30,       f"total_trades={m['total_trades']} (need >=30)"),
        (m["profit_factor"] >= 1.2,     f"profit_factor={m['profit_factor']} (need >=1.2)"),
        (m["win_rate"] >= 0.45,         f"win_rate={m['win_rate']} (need >=0.45)"),
        (m["avg_win_pct"] > abs(m["avg_loss_pct"]),
                                        f"avg_win={m['avg_win_pct']}% vs avg_loss={m['avg_loss_pct']}%"),
        (m["max_drawdown_pct"] >= -25.0, f"max_drawdown={m['max_drawdown_pct']}% (need >=-25%)"),
        (m["sharpe_ratio"] >= 0.3,      f"sharpe={m['sharpe_ratio']} (need >=0.3)"),
    ]
    failures = [msg for passed, msg in criteria if not passed]
    return len(failures) == 0, failures


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """
    Run the full backtest and print the performance report.

    Parameters: ALL_TICKERS, 2023-01-01 to 2024-12-31, 5-day hold, 5% stop.
    NOTE: Backtest applies breakout + RSI gates only.
          VWAP and sector filters are active in the live scanner.
    """
    print("=" * 65)
    print("SIGNAL BRAIN — SESSION 4 BACKTEST")
    print("Period : 2023-01-01 → 2024-12-31  (2 full years)")
    print("Gates  : Breakout (20d high + 1.5x volume) + RSI(14) 50–75")
    print("NOTE   : VWAP and sector filters active in live scanner only.")
    print("=" * 65)
    print(f"Scanning {len(config.ALL_TICKERS)} tickers …")

    trades = run_backtest(
        tickers=config.ALL_TICKERS,
        start=config.BACKTEST_START,
        end=config.BACKTEST_END,
        hold_days=config.BACKTEST_HOLD_DAYS,
        stop_loss_pct=config.BACKTEST_STOP_LOSS_PCT,
        commission_per_trade=config.BACKTEST_COMMISSION,
    )

    print(f"\nTotal signals detected: {len(trades)}\n")

    m = compute_metrics(trades)

    print("─" * 45)
    print("PERFORMANCE METRICS")
    print("─" * 45)
    for key, val in m.items():
        print(f"  {key:<28} {val}")

    if not trades.empty:
        print("\n─" * 23)
        print("TOP 5 BEST TRADES")
        print("─" * 45)
        best = trades.nlargest(5, "net_return_pct")[
            ["ticker", "signal_date", "entry_price", "exit_price", "net_return_pct", "exit_reason"]
        ]
        print(best.to_string(index=False))

        print("\n─" * 23)
        print("TOP 5 WORST TRADES")
        print("─" * 45)
        worst = trades.nsmallest(5, "net_return_pct")[
            ["ticker", "signal_date", "entry_price", "exit_price", "net_return_pct", "exit_reason"]
        ]
        print(worst.to_string(index=False))

        print("\n─" * 23)
        print("SIGNALS PER TICKER")
        print("─" * 45)
        counts = (
            trades.groupby("ticker")
            .size()
            .reset_index(name="signals")
            .sort_values("signals", ascending=False)
        )
        print(counts.to_string(index=False))

    passed, failures = _verdict(m)
    print("\n" + "=" * 65)
    if passed:
        print("VERDICT: PASS ✓  — All criteria met.")
    else:
        print("VERDICT: FAIL ✗  — Criteria not met:")
        for f in failures:
            print(f"  • {f}")
    print("=" * 65)


if __name__ == "__main__":
    main()
