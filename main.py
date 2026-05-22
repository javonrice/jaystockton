"""
main.py — Entry point for Signal Brain data pipeline (Session 1).

Starts an APScheduler blocking loop that fires run_scanner every 60 seconds.
Runs an initial scan immediately on startup so the database is seeded before
the first scheduled tick.

Usage:
    python main.py
"""

import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

import config
from feeds.market_data import init_db, run_scanner
from journal.logger import get_logger

logger = get_logger(__name__)


def _shutdown_handler(signum: int, frame: object) -> None:
    """Log shutdown signal and exit cleanly."""
    logger.info("Shutdown signal %d received — stopping Signal Brain.", signum)
    sys.exit(0)


def _validate_credentials() -> None:
    """Call credential getters early to surface missing .env values at startup."""
    config.get_alpaca_api_key()
    config.get_alpaca_secret_key()


def main() -> None:
    """Initialise resources and start the 60-second polling loop."""
    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    logger.info("Signal Brain starting up — Session 1 (data pipeline)")
    logger.info("Watching %d tickers", len(config.ALL_TICKERS))

    try:
        _validate_credentials()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    conn = init_db(config.DB_PATH)

    # Seed the database immediately — don't wait 60 seconds for the first tick.
    logger.info("Running initial scan...")
    run_scanner(conn)

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        func=run_scanner,
        trigger=IntervalTrigger(seconds=config.POLL_INTERVAL_SECONDS),
        args=[conn],
        id="bar_scanner",
        name="Alpaca bar scanner",
        max_instances=1,
        coalesce=True,
    )

    logger.info("Scheduler started — polling every %ds. Press Ctrl+C to stop.", config.POLL_INTERVAL_SECONDS)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Signal Brain stopped.")


if __name__ == "__main__":
    main()
