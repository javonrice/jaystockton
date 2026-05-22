"""
main.py — Entry point for Signal Brain (Sessions 1 + 2).

Two scheduled jobs:
  - bar_scanner: polls Alpaca every 60 seconds for minute bars (Session 1)
  - eod_scanner: fires at 16:05 ET daily to fetch daily bars and run
                 the breakout signal detector (Session 2)

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
from feeds.market_data import (
    fetch_all_daily_bars,
    init_daily_bars_table,
    init_db,
    run_scanner,
    store_daily_bars,
)
from journal.logger import get_logger, init_signals_table, store_signal
from signals.breakout import scan_all_breakouts

logger = get_logger(__name__)


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

    logger.info(
        "Scheduler started — minute bars every %ds, EOD scan at %02d:%02d ET.",
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
