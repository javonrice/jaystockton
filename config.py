"""
config.py — Centralized configuration for Signal Brain.

Reads all settings from environment variables populated by .env via python-dotenv.
No other module should call os.getenv or os.environ directly.

Requires:
    .env file (or Codespaces secrets) with ALPACA_API_KEY and ALPACA_SECRET_KEY.

Returns:
    Module-level constants and typed accessor functions for all settings.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=False)

# --- Alpaca API credentials (read lazily via functions to avoid import-time errors) ---

def get_alpaca_api_key() -> str:
    """Return the Alpaca API key. Raises ValueError if not set."""
    val = os.getenv("ALPACA_API_KEY", "")
    if not val:
        raise ValueError("ALPACA_API_KEY is not set. Check your .env file or Codespaces secrets.")
    return val


def get_alpaca_secret_key() -> str:
    """Return the Alpaca secret key. Raises ValueError if not set."""
    val = os.getenv("ALPACA_SECRET_KEY", "")
    if not val:
        raise ValueError("ALPACA_SECRET_KEY is not set. Check your .env file or Codespaces secrets.")
    return val


# --- Data feed ---
ALPACA_FEED: str = os.getenv("ALPACA_FEED", "iex")

# --- Database ---
DB_PATH: str = os.getenv("DB_PATH", "signal_brain.duckdb")

# --- Logging ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE: str = "logs/signal_brain.log"

# --- Scheduler ---
POLL_INTERVAL_SECONDS: int = 60

# --- Bars to fetch per cycle ---
# Fetch last 2 bars per ticker so a slow cycle doesn't miss the most recent completed bar.
BARS_LIVE_LIMIT: int = 2

# Bars to fetch when market is closed (fallback seed). 390 = one full trading day.
BARS_FALLBACK_LIMIT: int = int(os.getenv("BARS_FALLBACK_LIMIT", "390"))

# --- Ticker universe ---

TIER_1_TICKERS: list[str] = [
    "SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMD", "TSLA", "AMZN",
    "GOOGL", "META", "NFLX", "CRM", "ORCL", "ADBE", "QCOM", "INTC",
    "MU", "AVGO", "TSM", "ASML", "ARM", "SMCI",
]

TIER_2_TICKERS: list[str] = [
    "XLK", "SMH", "XLF", "XLE", "XBI", "XLV", "XLI", "XLY", "XLC", "ARKK",
]

ALL_TICKERS: list[str] = TIER_1_TICKERS + TIER_2_TICKERS

# --- Session 2: daily bars + breakout signal ---
DAILY_BAR_LIMIT: int = 30
VOLUME_RATIO_MIN: float = 1.5
BREAKOUT_LOOKBACK: int = 20
EOD_SCAN_HOUR: int = 16
EOD_SCAN_MINUTE: int = 5

# --- Session 3: momentum filters ---
RSI_PERIOD: int = 14
RSI_MIN: float = 50.0
RSI_MAX: float = 75.0
VWAP_MIN_BARS: int = 30

# --- Session 4: backtest ---
BACKTEST_START: str = "2023-01-01"
BACKTEST_END: str = "2024-12-31"
BACKTEST_HOLD_DAYS: int = 5
BACKTEST_STOP_LOSS_PCT: float = 0.05
BACKTEST_COMMISSION: float = 0.001

# --- Session 4b: ATR stop + earnings exclusion ---
BACKTEST_ATR_MULTIPLIER: float = 2.0
BACKTEST_ATR_PERIOD: int = 14
EARNINGS_WINDOW_DAYS: int = 5

SECTOR_MAP: dict[str, str | None] = {
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "XLK", "AMD": "XLK",
    "QCOM": "XLK", "INTC": "XLK", "MU": "XLK", "AVGO": "XLK",
    "TSM": "XLK", "ASML": "XLK", "ARM": "XLK", "SMCI": "XLK",
    "ADBE": "XLK", "CRM": "XLK", "ORCL": "XLK",
    "TSLA": "XLY", "AMZN": "XLY",
    "GOOGL": "XLC", "META": "XLC", "NFLX": "XLC",
    "SPY": None, "QQQ": None,
    "XLK": None, "SMH": None, "XLF": None, "XLE": None,
    "XBI": None, "XLV": None, "XLI": None, "XLY": None,
    "XLC": None, "ARKK": None,
}
