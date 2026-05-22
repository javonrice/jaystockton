"""
feeds/market_data.py — Alpaca REST API polling and DuckDB storage for Signal Brain.

Fetches minute bars and daily bars for every ticker in the watchlist via Alpaca's
StockHistoricalDataClient, stores them in a local DuckDB database,
and orchestrates the per-cycle scan called by APScheduler in main.py.

Requires:
    ALPACA_API_KEY and ALPACA_SECRET_KEY set in .env or environment.
    DuckDB database initialised via init_db() before calling store_bars().

Returns:
    Functions: is_market_open, init_db, init_daily_bars_table,
               fetch_bars, fetch_all_bars, store_bars,
               fetch_daily_bars, fetch_all_daily_bars, store_daily_bars,
               run_scanner.
"""

from __future__ import annotations

import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import duckdb
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import config
from journal.logger import get_logger

logger = get_logger(__name__)

_ET = ZoneInfo("America/New_York")


def _now_et() -> datetime.datetime:
    """Return current time in US/Eastern. Isolated for test patching."""
    return datetime.datetime.now(tz=_ET)


def is_market_open() -> bool:
    """
    Return True if the US equity market is currently open.

    Checks Eastern Time, Monday–Friday, 09:30–16:00.
    Does not account for market holidays.
    """
    now = _now_et()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return datetime.time(9, 30) <= t < datetime.time(16, 0)


def _build_client() -> StockHistoricalDataClient:
    """Build and return an authenticated Alpaca StockHistoricalDataClient."""
    return StockHistoricalDataClient(
        api_key=config.get_alpaca_api_key(),
        secret_key=config.get_alpaca_secret_key(),
    )


def init_db(db_path: str = config.DB_PATH) -> duckdb.DuckDBPyConnection:
    """
    Open or create the DuckDB database and ensure the bars table exists.

    Schema: ticker TEXT, timestamp TIMESTAMPTZ, open DOUBLE, high DOUBLE,
            low DOUBLE, close DOUBLE, volume BIGINT.
    A PRIMARY KEY on (ticker, timestamp) prevents duplicate rows.

    Args:
        db_path: Path to the DuckDB file, or ':memory:' for in-memory.

    Returns:
        Open DuckDB connection.
    """
    conn = duckdb.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bars (
            ticker    TEXT        NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL,
            open      DOUBLE      NOT NULL,
            high      DOUBLE      NOT NULL,
            low       DOUBLE      NOT NULL,
            close     DOUBLE      NOT NULL,
            volume    BIGINT      NOT NULL,
            PRIMARY KEY (ticker, timestamp)
        )
    """)
    logger.info("Database ready at %s", db_path)
    return conn


def fetch_bars(ticker: str, limit: int) -> Optional[pd.DataFrame]:
    """
    Fetch the most recent `limit` minute bars for a single ticker.

    Args:
        ticker: Stock symbol, e.g. 'AAPL'.
        limit: Number of recent bars to fetch.

    Returns:
        DataFrame with columns (ticker, timestamp, open, high, low, close, volume),
        or None if the API returns no data or raises an error.
    """
    try:
        client = _build_client()
        end = datetime.datetime.now(tz=datetime.timezone.utc)
        start = end - datetime.timedelta(minutes=limit + 10)

        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            feed=config.ALPACA_FEED,
            limit=limit,
        )
        bars = client.get_stock_bars(request)
        df: pd.DataFrame = bars.df

        if df.empty:
            logger.warning("No bars returned for %s", ticker)
            return None

        df = df.reset_index()

        # alpaca-py MultiIndex reset produces 'symbol' — rename to 'ticker'
        if "symbol" in df.columns:
            df = df.rename(columns={"symbol": "ticker"})

        df = df[["ticker", "timestamp", "open", "high", "low", "close", "volume"]]

        # Ensure timestamp is UTC-aware
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")

        df["volume"] = df["volume"].astype("int64")
        logger.info("Fetched %d bars for %s", len(df), ticker)
        return df

    except Exception as exc:
        logger.error("Failed to fetch bars for %s: %s", ticker, exc)
        return None


def fetch_all_bars(tickers: list[str], limit: int) -> dict[str, Optional[pd.DataFrame]]:
    """
    Fetch minute bars for every ticker in `tickers`.

    Each ticker is fetched independently — one failure never blocks the rest.

    Args:
        tickers: List of stock symbols.
        limit: Number of recent bars per ticker.

    Returns:
        Dict mapping ticker -> DataFrame (or None on error).
    """
    results: dict[str, Optional[pd.DataFrame]] = {}
    for ticker in tickers:
        results[ticker] = fetch_bars(ticker, limit)
    return results


def store_bars(conn: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    """
    Insert new bars from df into the database, skipping duplicates.

    Uses ON CONFLICT DO NOTHING against the PRIMARY KEY (ticker, timestamp).

    Args:
        conn: Open DuckDB connection with bars table initialised.
        df: DataFrame with columns matching the bars schema.

    Returns:
        Number of rows actually inserted (0 if all were duplicates).
    """
    if df.empty:
        return 0

    conn.register("_new_bars", df)
    try:
        before = conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        conn.execute("""
            INSERT INTO bars (ticker, timestamp, open, high, low, close, volume)
            SELECT ticker, timestamp, open, high, low, close, volume
            FROM _new_bars
            ON CONFLICT (ticker, timestamp) DO NOTHING
        """)
        after = conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        inserted = after - before
        if inserted > 0:
            logger.debug("Stored %d new bars (%d duplicates skipped)", inserted, len(df) - inserted)
        return inserted
    finally:
        conn.unregister("_new_bars")


def init_daily_bars_table(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Create the daily_bars table if it does not exist.

    Schema: ticker TEXT, date DATE, open/high/low/close DOUBLE, volume BIGINT.
    PRIMARY KEY on (ticker, date) prevents duplicate daily rows.

    Args:
        conn: Open DuckDB connection.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_bars (
            ticker  TEXT   NOT NULL,
            date    DATE   NOT NULL,
            open    DOUBLE NOT NULL,
            high    DOUBLE NOT NULL,
            low     DOUBLE NOT NULL,
            close   DOUBLE NOT NULL,
            volume  BIGINT NOT NULL,
            PRIMARY KEY (ticker, date)
        )
    """)
    logger.info("daily_bars table ready")


def fetch_daily_bars(ticker: str, limit: int) -> Optional[pd.DataFrame]:
    """
    Fetch the most recent `limit` completed daily bars for a single ticker.

    Args:
        ticker: Stock symbol, e.g. 'AAPL'.
        limit: Number of trading days to fetch.

    Returns:
        DataFrame with columns (ticker, date, open, high, low, close, volume),
        or None if the API returns no data or raises an error.
    """
    try:
        client = _build_client()
        end = datetime.datetime.now(tz=datetime.timezone.utc)
        start = end - datetime.timedelta(days=limit + 10)

        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=config.ALPACA_FEED,
            limit=limit,
        )
        bars = client.get_stock_bars(request)
        df: pd.DataFrame = bars.df

        if df.empty:
            logger.warning("No daily bars returned for %s", ticker)
            return None

        df = df.reset_index()
        if "symbol" in df.columns:
            df = df.rename(columns={"symbol": "ticker"})

        # Alpaca timestamps for daily bars are midnight UTC — cast to DATE.
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date
        df = df[["ticker", "date", "open", "high", "low", "close", "volume"]]
        df["volume"] = df["volume"].astype("int64")

        logger.info("Fetched %d daily bars for %s", len(df), ticker)
        return df

    except Exception as exc:
        logger.error("Failed to fetch daily bars for %s: %s", ticker, exc)
        return None


def fetch_all_daily_bars(tickers: list[str], limit: int) -> dict[str, Optional[pd.DataFrame]]:
    """
    Fetch daily bars for every ticker in `tickers`.

    Each ticker is fetched independently — one failure never blocks the rest.

    Args:
        tickers: List of stock symbols.
        limit: Number of recent trading days per ticker.

    Returns:
        Dict mapping ticker -> DataFrame (or None on error).
    """
    results: dict[str, Optional[pd.DataFrame]] = {}
    for ticker in tickers:
        results[ticker] = fetch_daily_bars(ticker, limit)
    return results


def store_daily_bars(conn: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> int:
    """
    Insert new daily bars from df into daily_bars, skipping duplicates.

    Uses ON CONFLICT DO NOTHING against PRIMARY KEY (ticker, date).

    Args:
        conn: Open DuckDB connection with daily_bars table initialised.
        df: DataFrame with columns matching the daily_bars schema.

    Returns:
        Number of rows actually inserted (0 if all were duplicates).
    """
    if df.empty:
        return 0

    conn.register("_new_daily_bars", df)
    try:
        before = conn.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]
        conn.execute("""
            INSERT INTO daily_bars (ticker, date, open, high, low, close, volume)
            SELECT ticker, date, open, high, low, close, volume
            FROM _new_daily_bars
            ON CONFLICT (ticker, date) DO NOTHING
        """)
        after = conn.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]
        return after - before
    finally:
        conn.unregister("_new_daily_bars")


def run_scanner(conn: duckdb.DuckDBPyConnection) -> None:
    """
    Execute one full data collection cycle for all tickers.

    When the market is open: fetches the 2 most recent minute bars per ticker.
    When the market is closed: fetches BARS_FALLBACK_LIMIT historical bars so
    the database is seeded with real data even during off-hours.

    Args:
        conn: Open DuckDB connection with bars table initialised.
    """
    if is_market_open():
        limit = config.BARS_LIVE_LIMIT
        logger.info("Market OPEN — fetching %d bars for %d tickers", limit, len(config.ALL_TICKERS))
    else:
        limit = config.BARS_FALLBACK_LIMIT
        logger.info(
            "Market CLOSED — seeding %d historical bars for %d tickers",
            limit,
            len(config.ALL_TICKERS),
        )

    results = fetch_all_bars(config.ALL_TICKERS, limit)
    total = 0
    for ticker, df in results.items():
        if df is not None:
            stored = store_bars(conn, df)
            total += stored
            if stored > 0:
                logger.info(
                    "STORED | %-6s | +%d bars | latest %s",
                    ticker,
                    stored,
                    df["timestamp"].max(),
                )

    logger.info("Scan complete — %d new bars stored across %d tickers", total, len(config.ALL_TICKERS))
