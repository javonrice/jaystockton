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

# Mega-cap tech
MEGA_CAP: list[str] = [
    "AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA", "NFLX",
    "ORCL", "ADBE", "CRM", "NOW", "SHOP",
]

# Semiconductors
SEMIS: list[str] = [
    "AMD", "INTC", "QCOM", "AVGO", "MU", "TSM", "ASML", "ARM", "SMCI",
    "AMAT", "LRCX", "KLAC", "MRVL", "MPWR",
]

# AI infrastructure
AI_INFRA: list[str] = [
    "PLTR", "AI", "PATH", "IONQ", "DELL", "PSTG", "CRWV", "CIEN",
]

# Cybersecurity
CYBER: list[str] = [
    "CRWD", "PANW", "FTNT", "ZS", "OKTA", "S", "CYBR", "NET", "RPD", "TENB",
]

# Chinese ADRs
CHINA_ADRS: list[str] = [
    "BABA", "JD", "PDD", "BIDU", "NIO", "LI", "XPEV", "BILI",
    "FUTU", "TCOM", "EDU", "VNET",
]

# Meme and retail momentum
MEME_MOMENTUM: list[str] = [
    "GME", "MSTR", "COIN", "HOOD", "SOFI", "RKLB", "ACHR", "JOBY",
]

# Biotech
BIOTECH: list[str] = [
    "MRNA", "BNTX", "REGN", "BIIB", "VRTX", "ILMN", "BEAM", "CRSP",
    "RXRX", "PACB",
]

# EV and clean energy
EV_CLEAN: list[str] = [
    "RIVN", "LCID", "CHPT", "PLUG", "ENPH", "SEDG", "RUN", "BE",
]

# Fintech
FINTECH: list[str] = [
    "V", "MA", "PYPL", "SQ", "AFRM", "UPST", "NU",
]

# Defense
DEFENSE: list[str] = [
    "LMT", "RTX", "NOC", "GD", "BA", "KTOS",
]

# Retail and consumer momentum
CONSUMER: list[str] = [
    "COST", "LULU", "NKE", "ONON", "CELH", "APP", "DECK",
]

# Sector ETFs — market context
SECTOR_ETFS: list[str] = [
    "SPY", "QQQ", "IWM", "XLK", "XLF", "XLE", "XBI", "XLV",
    "XLI", "XLY", "XLC", "SMH", "ARKK", "CIBR", "BOTZ",
]

# Legacy aliases — kept so Sessions 1-3 live scanner references don't break
TIER_1_TICKERS: list[str] = MEGA_CAP + SEMIS
TIER_2_TICKERS: list[str] = SECTOR_ETFS

ALL_TICKERS: list[str] = (
    MEGA_CAP + SEMIS + AI_INFRA + CYBER + CHINA_ADRS +
    MEME_MOMENTUM + BIOTECH + EV_CLEAN + FINTECH +
    DEFENSE + CONSUMER + SECTOR_ETFS
)

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

# --- Session 4c: out-of-sample ---
OOS_START: str = "2025-01-01"
OOS_END: str = "2025-12-31"

# --- Session 6: day trade engine ---

DAY_TRADE_UNIVERSE_TIER1: list[str] = [
    "NVDA", "AMD", "TSLA", "AAPL", "META", "AMZN", "GOOGL", "MSFT",
    "COIN", "PLTR", "MSTR", "NFLX", "CRWD", "PANW",
]

DAY_TRADE_UNIVERSE_TIER2: list[str] = [
    "RKLB", "ACHR", "JOBY", "FUTU", "BIDU", "BABA", "NIO", "XPEV",
    "GME", "HOOD", "SOFI", "MRNA", "CRSP", "RXRX", "APP", "KTOS",
    "MRVL", "ARM", "SMCI", "RIVN", "IONQ",
]

DAY_TRADE_UNIVERSE: list[str] = DAY_TRADE_UNIVERSE_TIER1 + DAY_TRADE_UNIVERSE_TIER2

GAP_MIN_PCT: float = 2.0           # minimum gap to be on watchlist
ORB_MINUTES: int = 15              # opening range window (minutes)
INTRADAY_VOLUME_MULT: float = 1.5  # volume multiplier for ORB confirmation
SIGNAL_WINDOW_END_HOUR: int = 11   # stop scanning after 11:30 AM ET
SIGNAL_WINDOW_END_MINUTE: int = 30
DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

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
