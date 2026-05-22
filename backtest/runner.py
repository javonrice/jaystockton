"""
backtest/runner.py — Sessions 4 + 4b: historical backtest of the two-gate signal.

Applies the breakout + RSI gates (Sessions 2+3) to 2+ years of yFinance
daily data. Session 4b adds ATR-based stop loss and earnings exclusion.

NOTE: Backtest applies breakout + RSI gates only.
      VWAP and sector filters are active in the live scanner.

Requires:
    yfinance>=0.2.40

Returns:
    fetch_historical_data, fetch_all_historical,
    compute_atr, fetch_earnings_dates, is_near_earnings,
    detect_breakout_historical, run_backtest, compute_metrics, main.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd
import yfinance as yf

import config
from journal.logger import get_logger

logger = get_logger(__name__)

# Signal gate constants (must match Session 3 values)
_RSI_PERIOD: int = 14
_RSI_MIN: float = 50.0
_RSI_MAX: float = 75.0
_VOLUME_RATIO_MIN: float = 1.5
_LOOKBACK: int = 20

# Hardcoded Session 4 baseline for comparison (run 2023-01-01 to 2024-12-31)
_BASELINE: dict[str, Any] = {
    "total_trades": 231,
    "win_rate": 0.5758,
    "avg_win_pct": 3.9655,
    "avg_loss_pct": -4.4188,
    "profit_factor": 1.2179,
    "max_drawdown_pct": -77.7649,
    "sharpe_ratio": 1.1507,
    "total_net_return_pct": 94.3683,
    "avg_stop_pct_implied": 5.00,
    "signals_skipped_earnings": "n/a",
}


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


# ── ATR ───────────────────────────────────────────────────────────────────────


def compute_atr(df: pd.DataFrame, idx: int, period: int = 14) -> Optional[float]:
    """
    Compute ATR(period) using Wilder smoothing at row idx.

    Requires at least period+1 rows (idx >= period) so that idx rows
    0..idx-1 supply prev_close for bar 1 and period TRs can be formed.
    True Range = max(high-low, |high-prev_close|, |low-prev_close|).

    Args:
        df: DataFrame with columns high, low, close (sorted ascending).
        idx: Row index to evaluate (inclusive upper bound of ATR window).
        period: Smoothing period (default 14).

    Returns:
        ATR value rounded to 4 decimal places, or None if insufficient data.
    """
    if idx < period:
        return None

    # Compute all TRs from bar 1 through bar idx using Wilder smoothing
    trs: list[float] = []
    for i in range(1, idx + 1):
        high = float(df.iloc[i]["high"])
        low = float(df.iloc[i]["low"])
        prev_close = float(df.iloc[i - 1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    # Wilder: initialize with simple average of first period TRs
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period

    return round(atr, 4)


# ── Earnings exclusion ────────────────────────────────────────────────────────


def fetch_earnings_dates(ticker: str, start: str, end: str) -> set[pd.Timestamp]:
    """
    Fetch earnings announcement dates for ticker within date range.

    Uses yf.Ticker(ticker).earnings_dates. Returns empty set on any error.

    Args:
        ticker: Stock symbol.
        start: Start date 'YYYY-MM-DD'.
        end: End date 'YYYY-MM-DD'.

    Returns:
        Set of timezone-naive UTC Timestamps within [start, end].
    """
    try:
        tick = yf.Ticker(ticker)
        dates_df = tick.earnings_dates
        if dates_df is None or (hasattr(dates_df, "empty") and dates_df.empty):
            return set()
        idx = dates_df.index
        if hasattr(idx, "tz") and idx.tz is not None:
            idx = idx.tz_convert("UTC").tz_localize(None)
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        filtered = idx[(idx >= start_ts) & (idx <= end_ts)]
        return set(filtered)
    except Exception as exc:
        logger.warning("fetch_earnings_dates failed for %s: %s", ticker, exc)
        return set()


def is_near_earnings(
    signal_date: Any,
    earnings_dates: set,
    window_days: int = 5,
) -> bool:
    """
    Return True if signal_date is within window_days calendar days of any earnings date.

    Args:
        signal_date: The signal date (date, Timestamp, or string).
        earnings_dates: Set of earnings Timestamps.
        window_days: Exclusion window in calendar days (symmetric, inclusive).

    Returns:
        True if signal should be skipped.
    """
    if not earnings_dates:
        return False
    signal_ts = pd.Timestamp(signal_date)
    for ed in earnings_dates:
        ed_ts = pd.Timestamp(ed)
        if abs((signal_ts - ed_ts).days) <= window_days:
            return True
    return False


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
    stop_loss_pct: float = 0.05,   # kept for reference — ATR path is used instead
    commission_per_trade: float = 0.001,
    atr_multiplier: float = 2.0,
    earnings_window_days: int = 5,
) -> pd.DataFrame:
    """
    Run the full backtest across all tickers for the given date range.

    Entry is next day's open after signal fires. Stop is ATR-based:
      stop_price = entry_price - atr_multiplier * ATR(14).
    Exit is the earlier of hold_days bars OR stop triggered.
    Signals within earnings_window_days of an earnings date are skipped.

    Args:
        tickers: List of symbols to scan.
        start: Start date 'YYYY-MM-DD'.
        end: End date 'YYYY-MM-DD'.
        hold_days: Maximum bars to hold.
        stop_loss_pct: Kept for API compatibility — not used (ATR stop is used).
        commission_per_trade: One-way commission fraction; round-trip = 2x.
        atr_multiplier: Stop distance = atr_multiplier * ATR(14).
        earnings_window_days: Skip signals within this many calendar days of earnings.

    Returns:
        DataFrame of all trades. attrs["signals_skipped_earnings"] contains count.
    """
    all_data = fetch_all_historical(tickers, start, end)
    trades: list[dict[str, Any]] = []
    skipped_earnings = 0

    for ticker, df in all_data.items():
        if df is None or len(df) < 30:
            logger.debug("Skipping %s: insufficient data", ticker)
            continue

        earnings = fetch_earnings_dates(ticker, start, end)
        n = len(df)

        for idx in range(_LOOKBACK + _RSI_PERIOD, n - 1):
            signal = detect_breakout_historical(df, idx)
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
                "atr_at_entry": atr,
                "stop_price": round(stop_price, 4),
                "stop_pct_implied": round(stop_pct_implied * 100, 4),
            })

    result = pd.DataFrame(trades)
    result.attrs["signals_skipped_earnings"] = skipped_earnings
    return result


# ── Performance metrics ───────────────────────────────────────────────────────


def compute_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    """
    Compute the full performance report from a trades DataFrame.

    Max drawdown uses an equity curve (multiplicative, equal position sizing)
    so it is expressed as a percentage of peak equity — not raw cumulative points.

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

    # Equity-curve max drawdown: $1 start, multiplicative per-trade returns
    equity = [1.0]
    for r in rets:
        equity.append(equity[-1] * (1.0 + r / 100.0))
    equity_s = pd.Series(equity)
    peak = equity_s.cummax()
    dd_pct = (equity_s - peak) / peak * 100.0
    max_dd = float(dd_pct.min())

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


# ── Verdict helpers ───────────────────────────────────────────────────────────


def _verdict_4b(m: dict[str, Any]) -> tuple[bool, list[str]]:
    """4b PASS criteria (tighter than 4a; avg_win/loss ratio is key gate)."""
    criteria = [
        (m["total_trades"] >= 20,
         f"total_trades={m['total_trades']} (need >=20)"),
        (m["profit_factor"] >= 1.3,
         f"profit_factor={m['profit_factor']} (need >=1.3)"),
        (m["avg_win_pct"] > abs(m["avg_loss_pct"]),
         f"avg_win={m['avg_win_pct']}% vs avg_loss={m['avg_loss_pct']}% (win must exceed loss)"),
        (m["sharpe_ratio"] >= 0.5,
         f"sharpe={m['sharpe_ratio']} (need >=0.5)"),
    ]
    failures = [msg for passed, msg in criteria if not passed]
    return len(failures) == 0, failures


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    """
    Run the 4b backtest and print a side-by-side comparison with the 4a baseline.

    Gates: Breakout + RSI (unchanged from 4a).
    Stop:  ATR(14) x 2.0 (replaces fixed 5%).
    Skip:  Signals within 5 calendar days of an earnings announcement.

    NOTE: Backtest applies breakout + RSI gates only.
          VWAP and sector filters are active in the live scanner.
    """
    print("=" * 65)
    print("SIGNAL BRAIN — SESSION 4b BACKTEST")
    print("Period : 2023-01-01 → 2024-12-31  (2 full years)")
    print("Gates  : Breakout (20d high + 1.5x vol) + RSI(14) 50–75")
    print("Stop   : ATR(14) × 2.0  (replaces fixed 5%)")
    print("Excl.  : ±5 days around earnings announcements")
    print("NOTE   : VWAP and sector filters active in live scanner only.")
    print("=" * 65)
    print(f"Scanning {len(config.ALL_TICKERS)} tickers …\n")

    trades_4b = run_backtest(
        tickers=config.ALL_TICKERS,
        start=config.BACKTEST_START,
        end=config.BACKTEST_END,
        hold_days=config.BACKTEST_HOLD_DAYS,
        stop_loss_pct=config.BACKTEST_STOP_LOSS_PCT,
        commission_per_trade=config.BACKTEST_COMMISSION,
        atr_multiplier=config.BACKTEST_ATR_MULTIPLIER,
        earnings_window_days=config.EARNINGS_WINDOW_DAYS,
    )

    m4b = compute_metrics(trades_4b)
    skipped = trades_4b.attrs.get("signals_skipped_earnings", 0)
    avg_stop_4b = (
        round(float(trades_4b["stop_pct_implied"].mean()), 2)
        if not trades_4b.empty and "stop_pct_implied" in trades_4b.columns
        else 0.0
    )

    # ── Side-by-side comparison ────────────────────────────────────────────
    W = 18
    print("=" * 65)
    print("SESSION 4 BASELINE vs SESSION 4b COMPARISON")
    print("=" * 65)
    header = f"{'Metric':<30} {'BASELINE':>{W}} {'4b (ATR+Earnings)':>{W}}"
    print(header)
    print("─" * 65)

    rows = [
        ("total_trades",            _BASELINE["total_trades"],          m4b["total_trades"]),
        ("win_rate",                _BASELINE["win_rate"],               m4b["win_rate"]),
        ("avg_win_pct",             _BASELINE["avg_win_pct"],            m4b["avg_win_pct"]),
        ("avg_loss_pct",            _BASELINE["avg_loss_pct"],           m4b["avg_loss_pct"]),
        ("profit_factor",           _BASELINE["profit_factor"],          m4b["profit_factor"]),
        ("max_drawdown_pct",        _BASELINE["max_drawdown_pct"],       m4b["max_drawdown_pct"]),
        ("sharpe_ratio",            _BASELINE["sharpe_ratio"],           m4b["sharpe_ratio"]),
        ("total_net_return_pct",    _BASELINE["total_net_return_pct"],   m4b["total_net_return_pct"]),
        ("signals_skipped_earnings", _BASELINE["signals_skipped_earnings"], skipped),
        ("avg_stop_pct_implied",    f"{_BASELINE['avg_stop_pct_implied']:.2f}%", f"{avg_stop_4b:.2f}%"),
    ]
    for label, base_val, new_val in rows:
        print(f"  {label:<28} {str(base_val):>{W}} {str(new_val):>{W}}")

    # Baseline verdict (4a criteria)
    baseline_4a_passed = (
        _BASELINE["total_trades"] >= 30
        and _BASELINE["profit_factor"] >= 1.2
        and _BASELINE["win_rate"] >= 0.45
        and _BASELINE["avg_win_pct"] > abs(_BASELINE["avg_loss_pct"])
        and _BASELINE["max_drawdown_pct"] >= -25.0
        and _BASELINE["sharpe_ratio"] >= 0.3
    )
    print(f"\n  BASELINE VERDICT : {'PASS ✓' if baseline_4a_passed else 'FAIL ✗'}")

    passed_4b, failures_4b = _verdict_4b(m4b)
    if passed_4b:
        print("  4b VERDICT       : PASS ✓")
    else:
        print("  4b VERDICT       : FAIL ✗")
        for f in failures_4b:
            print(f"    • {f}")
    print("=" * 65)

    if not trades_4b.empty:
        print("\n─" * 23)
        print("TOP 5 BEST TRADES")
        print("─" * 45)
        cols = ["ticker", "signal_date", "entry_price", "exit_price",
                "net_return_pct", "stop_pct_implied", "exit_reason"]
        print(trades_4b.nlargest(5, "net_return_pct")[cols].to_string(index=False))

        print("\n─" * 23)
        print("TOP 5 WORST TRADES")
        print("─" * 45)
        print(trades_4b.nsmallest(5, "net_return_pct")[cols].to_string(index=False))

        print("\n─" * 23)
        print("SIGNALS PER TICKER")
        print("─" * 45)
        counts = (
            trades_4b.groupby("ticker")
            .size()
            .reset_index(name="signals")
            .sort_values("signals", ascending=False)
        )
        print(counts.to_string(index=False))


if __name__ == "__main__":
    main()
