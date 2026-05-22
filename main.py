"""
main.py — Entry point for Signal Brain (Sessions 1–6).

Scheduled jobs:
  bar_scanner   — every 60 s during market hours (minute bars, Session 1)
  eod_scanner   — 16:05 ET daily (daily bars + swing breakout, Session 2)
  premarket_job — 09:00 ET daily (pre-market gap scanner, Session 6)
  open_job      — 09:30 ET daily (record opens, reset state, Session 6)
  intraday_job  — 09:45 ET + every 5 min to 11:30 ET (ORB scanner, Session 6)

Usage:
    python main.py
"""

import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import duckdb

import config
from alerts.discord import send_discord_alert, send_premarket_summary
from feeds.market_data import (
    fetch_all_daily_bars,
    init_daily_bars_table,
    init_db,
    run_scanner,
    store_daily_bars,
)
from journal.logger import get_logger, init_signals_table, store_signal
from signals.breakout import scan_all_breakouts
from signals.daytrader import (
    build_discord_message,
    scan_orb_signals,
    scan_premarket_gaps,
)

logger = get_logger(__name__)

# ── Day-trade state (resets each morning at market open) ──────────────────────
# These are module-level so all scheduled job closures share the same objects.
_gap_watchlist: list[dict] = []
_opening_ranges: dict[str, dict] = {}


def _shutdown_handler(signum: int, frame: object) -> None:
    """Log shutdown signal and exit cleanly."""
    logger.info("Shutdown signal %d received — stopping Signal Brain.", signum)
    sys.exit(0)


def _validate_credentials() -> None:
    """Call credential getters early to surface missing env values at startup."""
    config.get_alpaca_api_key()
    config.get_alpaca_secret_key()


def run_eod_scan(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Fetch fresh daily bars for all tickers, run breakout scan, log results.

    Called by APScheduler at 16:05 ET. Stores any signals found to DuckDB.
    """
    logger.info("EOD scan — fetching daily bars for %d tickers", len(config.ALL_TICKERS))
    results = fetch_all_daily_bars(config.ALL_TICKERS, config.DAILY_BAR_LIMIT)

    stored_total = 0
    for ticker, df in results.items():
        if df is not None:
            stored_total += store_daily_bars(conn, df)
    logger.info("Daily bars: %d new rows stored", stored_total)

    signals = scan_all_breakouts(conn)

    if not signals:
        logger.info("NO SIGNAL — 0 breakouts detected across %d tickers", len(config.ALL_TICKERS))
        return

    for sig in signals:
        store_signal(conn, sig)
        logger.info(
            "SIGNAL | %s | %s | %s | close=%.2f | vol_ratio=%.2fx | %s",
            sig["ticker"], sig["signal_type"], sig["direction"],
            sig["close"], sig["volume_ratio"], sig["date"],
        )


def run_premarket_scan(conn: duckdb.DuckDBPyConnection) -> None:
    """
    9:00 AM ET — scan DAY_TRADE_UNIVERSE for pre-market gaps.

    Populates _gap_watchlist with tickers gapping >= GAP_MIN_PCT.
    Sends Discord pre-market summary.
    """
    global _gap_watchlist
    logger.info(
        "Pre-market scan — scanning %d tickers for gaps >= %.1f%%",
        len(config.DAY_TRADE_UNIVERSE), config.GAP_MIN_PCT,
    )
    _gap_watchlist = scan_premarket_gaps(config.DAY_TRADE_UNIVERSE, conn)
    logger.info("Watchlist for today: %s", [g["ticker"] for g in _gap_watchlist])
    send_premarket_summary(_gap_watchlist)


def run_market_open(conn: duckdb.DuckDBPyConnection) -> None:  # noqa: ARG001
    """
    9:30 AM ET — reset opening range state for a fresh trading day.
    """
    global _opening_ranges
    _opening_ranges = {}
    logger.info("Market open — opening range state reset for %d candidates",
                len(_gap_watchlist))


def run_intraday_scan(conn: duckdb.DuckDBPyConnection) -> None:
    """
    9:45 AM ET and every 5 minutes to 11:30 AM ET.

    Scans the morning watchlist for ORB signals. Sends Discord alert for each.
    Stops firing after SIGNAL_WINDOW_END_HOUR:SIGNAL_WINDOW_END_MINUTE ET.
    """
    import datetime
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
    now_et = datetime.datetime.now(tz=_ET)

    end_h = config.SIGNAL_WINDOW_END_HOUR
    end_m = config.SIGNAL_WINDOW_END_MINUTE
    if (now_et.hour, now_et.minute) > (end_h, end_m):
        logger.debug("Past signal window (%02d:%02d ET) — skipping intraday scan",
                     end_h, end_m)
        return

    if not _gap_watchlist:
        logger.debug("No gap candidates — nothing to scan")
        return

    signals = scan_orb_signals(_gap_watchlist, conn, _opening_ranges)
    for sig in signals:
        msg = build_discord_message(sig)
        send_discord_alert(msg)


def main() -> None:
    """Initialise resources and start the scheduler loop."""
    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    logger.info("Signal Brain starting up — Sessions 1+2 (data pipeline + breakout signals)")
    logger.info("Watching %d tickers", len(config.ALL_TICKERS))

    try:
        _validate_credentials()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    conn = init_db(config.DB_PATH)
    init_daily_bars_table(conn)
    init_signals_table(conn)

    logger.info("Running initial minute bar scan...")
    run_scanner(conn)

    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        func=run_scanner,
        trigger=IntervalTrigger(seconds=config.POLL_INTERVAL_SECONDS),
        args=[conn],
        id="bar_scanner",
        name="Alpaca minute bar scanner",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        func=run_eod_scan,
        trigger=CronTrigger(
            hour=config.EOD_SCAN_HOUR,
            minute=config.EOD_SCAN_MINUTE,
            timezone="America/New_York",
        ),
        args=[conn],
        id="eod_scanner",
        name="EOD breakout scanner",
        max_instances=1,
    )

    # ── Session 6: day trade jobs ──────────────────────────────────────────
    _ET = "America/New_York"

    scheduler.add_job(
        func=run_premarket_scan,
        trigger=CronTrigger(hour=9, minute=0, timezone=_ET),
        args=[conn],
        id="premarket_scanner",
        name="Pre-market gap scanner",
        max_instances=1,
    )

    scheduler.add_job(
        func=run_market_open,
        trigger=CronTrigger(hour=9, minute=30, timezone=_ET),
        args=[conn],
        id="market_open",
        name="Market open state reset",
        max_instances=1,
    )

    # 9:45 AM — first ORB check (15 min of opening range data collected)
    scheduler.add_job(
        func=run_intraday_scan,
        trigger=CronTrigger(hour=9, minute=45, timezone=_ET),
        args=[conn],
        id="intraday_first",
        name="ORB first check",
        max_instances=1,
    )

    # 9:50 AM to 11:30 AM — every 5 minutes
    scheduler.add_job(
        func=run_intraday_scan,
        trigger=CronTrigger(
            hour="9-11",
            minute="50,55,0,5,10,15,20,25,30",
            timezone=_ET,
        ),
        args=[conn],
        id="intraday_scanner",
        name="ORB intraday scanner",
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        "Scheduler started — minute bars every %ds, EOD scan at %02d:%02d ET, "
        "ORB scanner 09:45–11:30 ET.",
        config.POLL_INTERVAL_SECONDS,
        config.EOD_SCAN_HOUR,
        config.EOD_SCAN_MINUTE,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Signal Brain stopped.")


if __name__ == "__main__":
    main()
