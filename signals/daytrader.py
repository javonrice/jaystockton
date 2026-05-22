"""
signals/daytrader.py — Session 6: day trade scanning logic.

Pre-market gap scanner (9:00 AM ET) and ORB scanner (9:45–11:30 AM ET).
Stores signals to DuckDB and builds Discord alert messages.

Requires:
    DuckDB connection with daily_bars table.
    Alpaca credentials in environment.

Returns:
    scan_premarket_gaps, scan_orb_signals, build_discord_message.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import duckdb

import config
from feeds.intraday import (
    check_orb_signal,
    compute_opening_range,
    compute_premarket_gap,
    fetch_intraday_bars,
    fetch_premarket_bars,
    get_prev_close,
)
from journal.logger import get_logger, store_signal

logger = get_logger(__name__)

_ET = ZoneInfo("America/New_York")


# ── Gap scanner ────────────────────────────────────────────────────────────────


def scan_premarket_gaps(
    tickers: list[str], conn: duckdb.DuckDBPyConnection
) -> list[dict[str, Any]]:
    """
    Runs at 9:00 AM ET. Scans all tickers for meaningful pre-market gaps.

    For each ticker:
        1. Fetch pre-market bars from Alpaca.
        2. Look up previous close from daily_bars in DuckDB.
        3. Compute gap statistics.
        4. Keep only tickers with gap_pct >= GAP_MIN_PCT.

    Args:
        tickers: Tickers to scan.
        conn: DuckDB connection with daily_bars table.

    Returns:
        List of gap dicts sorted by gap_pct descending. Each dict has keys:
        ticker, gap_pct, premarket_volume, premarket_high, premarket_low,
        premarket_last, gap_direction.
    """
    candidates: list[dict[str, Any]] = []

    for ticker in tickers:
        try:
            prev_close = get_prev_close(ticker, conn)
            if prev_close is None or prev_close <= 0:
                logger.debug("No prev close for %s — skipping gap scan", ticker)
                continue

            bars = fetch_premarket_bars(ticker)
            if bars is None or bars.empty:
                logger.debug("No pre-market bars for %s", ticker)
                continue

            gap = compute_premarket_gap(ticker, prev_close, bars)
            if gap["gap_pct"] >= config.GAP_MIN_PCT:
                candidates.append(gap)
                logger.info(
                    "GAP CANDIDATE | %s | +%.2f%% | PM high=%.2f | PM vol=%d",
                    ticker, gap["gap_pct"], gap["premarket_high"], gap["premarket_volume"],
                )
        except Exception as exc:
            logger.error("scan_premarket_gaps failed for %s: %s", ticker, exc)

    candidates.sort(key=lambda g: g["gap_pct"], reverse=True)
    logger.info("Pre-market scan complete — %d gap candidates", len(candidates))
    return candidates


# ── ORB scanner ───────────────────────────────────────────────────────────────


def scan_orb_signals(
    watchlist: list[dict[str, Any]],
    conn: duckdb.DuckDBPyConnection,
    opening_ranges: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Runs every 5 minutes from 9:45–11:30 AM ET.

    For each ticker on the watchlist:
        1. Fetch intraday bars from market open.
        2. Compute (or re-use) the opening range.
        3. Run check_orb_signal().
        4. Store any new signals to DuckDB.

    Args:
        watchlist: List of gap dicts from scan_premarket_gaps().
        conn: DuckDB connection with signals table.
        opening_ranges: Mutable dict keyed by ticker → cached opening range.
                        Populated and reused across repeated calls.

    Returns:
        List of signal dicts that fired this cycle.
    """
    fired: list[dict[str, Any]] = []

    today = datetime.date.today()
    market_open_et = datetime.datetime.combine(
        today, datetime.time(9, 30), tzinfo=_ET
    )

    # Fetch SPY context once per cycle
    spy_bars = fetch_intraday_bars("SPY", market_open_et)
    spy_prev_close = get_prev_close("SPY", conn) or 0.0
    spy_current_close = (
        float(spy_bars["close"].iloc[-1]) if spy_bars is not None and not spy_bars.empty
        else 0.0
    )

    for gap in watchlist:
        ticker = gap["ticker"]
        try:
            bars = fetch_intraday_bars(ticker, market_open_et)
            if bars is None or bars.empty:
                continue

            # Build or reuse opening range
            if ticker not in opening_ranges:
                opening_ranges[ticker] = compute_opening_range(
                    bars, market_open_et, minutes=config.ORB_MINUTES
                )

            or_data = opening_ranges[ticker]
            prev_close = get_prev_close(ticker, conn) or 0.0

            signal = check_orb_signal(
                ticker=ticker,
                bars=bars,
                opening_range=or_data,
                prev_close=prev_close,
                gap=gap,
                spy_prev_close=spy_prev_close,
                spy_current_close=spy_current_close,
            )
            if signal is None:
                continue

            fired.append(signal)
            logger.info(
                "ORB SIGNAL | %s | price=%.2f | gap=+%.2f%% | vol_ratio=%.1fx",
                ticker, signal["price"], signal["gap_pct"], signal["volume_ratio"],
            )

            # Store in DuckDB — convert to signals table format
            db_signal = {
                "ticker": ticker,
                "date": today,
                "signal_type": signal["signal_type"],
                "direction": signal["direction"],
                "close": signal["price"],
                "volume": 0,
                "avg_volume": 0.0,
                "volume_ratio": signal["volume_ratio"],
                "high_20d": signal["or_high"],
            }
            store_signal(conn, db_signal)

        except Exception as exc:
            logger.error("scan_orb_signals failed for %s: %s", ticker, exc)

    return fired


# ── Discord message builder ───────────────────────────────────────────────────


def build_discord_message(signal: dict[str, Any]) -> str:
    """
    Format an ORB signal dict into a clean Discord alert message.

    Args:
        signal: Output of check_orb_signal().

    Returns:
        Formatted string ready to send as a Discord message.
    """
    ticker = signal["ticker"]
    price = signal["price"]
    gap_pct = signal["gap_pct"]
    or_high = signal["or_high"]
    vwap = signal["vwap"]
    volume_ratio = signal["volume_ratio"]
    stop = signal["suggested_stop"]

    ts = signal.get("timestamp", "")
    if hasattr(ts, "astimezone"):
        try:
            ts_et = ts.astimezone(_ET)
            ts_str = ts_et.strftime("%-I:%M %p ET")
        except Exception:
            ts_str = str(ts)
    else:
        ts_str = str(ts)

    return (
        f"🚨 SIGNAL: {ticker} ORB BREAKOUT\n"
        f"\n"
        f"Price: ${price:.2f}\n"
        f"Gap: +{gap_pct:.1f}% from yesterday\n"
        f"Broke above: ${or_high:.2f} (opening range high)\n"
        f"VWAP: ${vwap:.2f} ✅ price above\n"
        f"Volume: {volume_ratio:.1f}x normal\n"
        f"Stop level: ${stop:.2f} (opening range low)\n"
        f"\n"
        f"Time: {ts_str}"
    )
