# Signal Brain — Claude Code Handoff Document
> Read this entire file before writing a single line of code.
> This is the source of truth for every build decision.

---

## What We Are Building

**Signal Brain** is a personal intraday stock signal platform.

It watches 500-2,000 tickers simultaneously during market hours, detects specific technical setups confirmed by volume, momentum, options flow, and sector context, then delivers a single actionable Discord message telling the user exactly what to consider trading and exactly why.

**The entire product is the quality of the Discord message.**

Everything we build exists to make that message trustworthy, specific, and timely. If the message is good, the product works. If the message is noise, nothing else matters.

---

## The Target Output

Every component exists to produce this:

```
🟢  SIGNAL FIRED  ·  HIGH CONFIDENCE

Ticker:    AMD  (Advanced Micro Devices)
Action:    BUY CALL
Strike:    $165
Expiry:    June 27, 2026
Entry:     $163.40  (current ask)
Stop:      $161.80  (below breakout level)
Target:    $167.50  (next resistance)

WHY THIS FIRED:
  ✓ Broke 20-day resistance at $163.10 on 2.8x avg volume
  ✓ RSI at 58 and rising — not yet overbought
  ✓ Price above VWAP — buyers in control
  ✓ Unusual call volume: $165 strike 6x open interest
  ✓ SMH (sector ETF) up 1.2% today — tailwind confirmed

NEWS (context only — not the trigger):
  Wells Fargo upgrade noted 14 min ago [BULLISH]

Signals aligned: 5/5   Confidence: HIGH
Logged: #signal_247  ·  09:42:17 EST
```

---

## The Brain — Seven Layers

Signals fire from logic, not news. News is context only, never a trigger.

### Layer 1 — Price & Chart Structure (TRIGGER LAYER)
- Detect breakouts above 20-day high on 5-minute bars
- Detect VWAP reclaims after 30+ minutes below VWAP
- OSS: `vectorbt` + `pandas-ta` + `TA-Lib`
- Data: Alpaca Markets API (free real-time IEX)

### Layer 2 — Volume Confirmation (REQUIRED FILTER)
- No price signal advances without volume confirmation
- Minimum 1.5x average volume to qualify
- 2x+ elevates confidence score
- OSS: `pandas-ta` volume indicators

### Layer 3 — Momentum (CONFIRMATION LAYER)
- RSI(14) between 45-75: bullish zone, not overbought
- MACD histogram direction confirmation
- Sector ETF positive on the day
- OSS: `pandas-ta`

### Layer 4 — Options Flow (SMART MONEY LAYER)
- Call volume > open interest on specific strike = new positioning
- Unusual volume/OI ratio detection
- OSS: `yfinance` options chains + custom anomaly detector
- Note: yFinance options data is delayed ~15 min. Confirmatory, not predictive.

### Layer 5 — Sector & Market Context (ENVIRONMENT LAYER)
- Sector ETF direction and strength
- SPY/QQQ trend check
- VIX level check (high VIX = reduce confidence)
- Market regime classification
- OSS: `yfinance` ETF monitoring

### Layer 6 — Reasoning Engine (FUSION LAYER)
- Takes structured output from all 5 layers
- Scores confluence (1 point per layer that fires)
- Decides whether alert threshold is met
- Writes the human-readable Discord message
- Tool: Claude API via `anthropic` SDK
- Model: `claude-haiku-4-5-20251001` (fast, cheap, sufficient for structured reasoning)

### Layer 7 — News Context (ICING ONLY — NEVER TRIGGER)
- Appended AFTER signal fires from Layers 1-5
- FinBERT classifies recent headlines for the ticker
- SEC EDGAR real-time filings checked
- If no news: section omitted entirely
- OSS: `ProsusAI/finBERT` via HuggingFace + SEC EDGAR API + `newsapi-python`

---

## Confidence Scoring

| Score | Level | Action |
|-------|-------|--------|
| 1-2 / 5 | LOW | No alert sent |
| 3 / 5 | MEDIUM | Alert sent with caution flag |
| 4-5 / 5 | HIGH | Full alert sent |

---

## Negative Filters — When NOT to Alert

These conditions suppress signals regardless of confluence score:

- RSI above 80 at trigger time (overbought)
- VIX above 30 (high volatility, all signals suppressed)
- First 15 minutes of market open: 9:30-9:45am EST (too volatile)
- Last 15 minutes before close: 3:45-4:00pm EST (liquidity drop)
- Earnings within 48 hours (binary event risk — flag prominently instead)
- Average daily volume < 500,000 shares (too illiquid)
- Options bid-ask spread > 15% of mid price (too expensive to enter)

---

## Repo Structure

```
signal-brain/
├── CLAUDE.md              ← YOU ARE HERE. Read before every session.
├── README.md              ← Project overview
├── requirements.txt       ← All dependencies
├── .env.example           ← API key template (never commit real keys)
├── config.py              ← All parameters and settings
├── main.py                ← Entry point
├── feeds/
│   ├── __init__.py
│   └── market_data.py     ← Alpaca connector, bar fetching, universe management
├── signals/
│   ├── __init__.py
│   ├── breakout.py        ← Layer 1+2: price breakout + volume confirmation
│   └── momentum.py        ← Layer 3: RSI, MACD, VWAP, sector check
├── options/
│   ├── __init__.py
│   └── flow.py            ← Layer 4: options chain anomaly detection
├── fusion/
│   ├── __init__.py
│   └── engine.py          ← Layer 6: Claude API reasoning + alert composition
├── news/
│   ├── __init__.py
│   └── sentiment.py       ← Layer 7: FinBERT + EDGAR + NewsAPI
├── alerts/
│   ├── __init__.py
│   └── discord.py         ← Discord webhook formatter and sender
├── journal/
│   ├── __init__.py
│   └── logger.py          ← Dual-output logging (console + rotating file)
├── backtest/
│   ├── __init__.py
│   └── runner.py          ← vectorbt backtest engine
└── tests/
    ├── conftest.py
    ├── test_feeds.py
    ├── test_signals.py
    ├── test_options.py
    ├── test_fusion.py
    └── test_alerts.py
```

---

## Build Phases

We build in strict phases. Do not jump ahead.

### Phase 1 — Scanner Foundation (CURRENT PHASE)
**Goal:** Get data flowing reliably. Detect first signals. Log to file.
**Done when:** System scans 500 tickers, detects breakout candidates, logs results to DuckDB without crashing.

### Phase 2 — Backtest Validation
**Goal:** Prove signal logic has edge on historical data before trusting it live.
**Done when:** At least one signal type shows positive expected value on out-of-sample data.

### Phase 3 — Paper Trading with Discord Alerts
**Goal:** Run live signals during market hours, send real Discord messages, track every outcome.
**Done when:** 100+ signals logged with outcomes. Win rate, EV, and profit factor calculated.

### Phase 4 — Live Shadow Validation
**Goal:** Evaluate execution realism. Could the trade actually have been taken?
**Done when:** Slippage, timing, and spread analysis complete across 30+ trading days.

---

## Session Build Plan

Build one session at a time. Complete each session fully before starting the next.

| Session | Goal | Deliverable | Do NOT touch |
|---------|------|-------------|--------------|
| 1 | Data pipeline | Alpaca pulls minute bars for 500 tickers, stores in DuckDB, prints confirmation | Signal logic |
| 2 | First signal | 20-day breakout + 1.5x volume detection on live data, logged to file | News, options, alerts |
| 3 | Momentum layer | Add RSI + VWAP + sector ETF check to Session 2 candidates | Options, alerts, LLM |
| 4 | Backtest | Run Sessions 2-3 signal logic on 2 years yFinance data via vectorbt | Live data changes |
| 5 | Options layer | Add yFinance options chain anomaly detection | LLM, Discord |
| 6 | Fusion + Claude API | Wire all layers into Claude API reasoning engine, generate alert payload | Discord formatting |
| 7 | Discord alerts | Format and send Discord messages, append FinBERT news context | Position sizing |
| 8 | Journal | Log every alert to DuckDB with outcome tracking, build performance report | Nothing — required |

---

## Current Session: SESSION 1 ✅ (complete when success test passes)

### Goal
Build the data pipeline only. Nothing else.

### Exact Deliverable
A running Python script that:
1. Connects to Alpaca Markets API using credentials from `.env`
2. Pulls real-time minute bars for a watchlist of 32 tickers
3. Stores each bar in a local DuckDB database with schema: `(ticker, timestamp, open, high, low, close, volume)`
4. Prints a confirmation line to console and log file when new bars arrive
5. Handles connection errors gracefully without crashing

### Success Test
Run this query and get clean data back:
```sql
SELECT * FROM bars WHERE ticker='AAPL' ORDER BY timestamp DESC LIMIT 10;
```

### Session 1 is complete when
- Script runs for 30 minutes during market hours without crashing
- DuckDB file contains clean OHLCV data for all tickers
- Above query returns 10 clean rows for AAPL
- All functions have type hints and tests pass

### Do NOT build in Session 1
- Any signal detection logic
- Any alert or Discord logic
- Any LLM or Claude API calls
- Any news or sentiment processing
- Any options logic

---

## The Ticker Universe

Start with this universe. Expand after Session 1 is stable.

**Tier 1 — Always scan (highest options liquidity):**
SPY, QQQ, AAPL, MSFT, NVDA, AMD, TSLA, AMZN, GOOGL, META, NFLX, CRM,
ORCL, ADBE, QCOM, INTC, MU, AVGO, TSM, ASML, ARM, SMCI

**Tier 2 — Sector ETFs (for Layer 5 context):**
XLK, SMH, XLF, XLE, XBI, XLV, XLI, XLY, XLC, ARKK

**Tier 3 — High volume mid-caps (add after Tier 1 stable):**
Top 200 by 30-day average options volume from yFinance

**Full universe target:** 500 tickers by Session 2, 2,000 by Phase 3

---

## Signal Logic — Precise Rules

### Signal Type 1: Volume Breakout (PRIMARY)
```
TRIGGER:     Price closes above 20-day highest high on current 5-min bar
VOLUME:      Current 5-min volume > 1.5x time-normalized average
MOMENTUM:    RSI(14) between 45 and 75
VWAP:        Price above VWAP at trigger time
SECTOR:      Sector ETF positive on day (not down > -0.5%)
OPTIONS:     Call volume on nearest ATM strike > 1.5x 5-day avg (if available)
STOP:        1 ATR below breakout candle low
TARGET:      Next resistance level on daily chart
INVALIDATION: Price closes back below breakout level on next 5-min bar
```

### Signal Type 2: VWAP Reclaim (SECONDARY)
```
TRIGGER:     Price crosses above VWAP after 30+ minutes below VWAP
VOLUME:      Cross candle volume > 1.3x average for time period
MOMENTUM:    MACD histogram turning positive at time of cross
CONTEXT:     SPY not making lower lows on 5-min
STOP:        VWAP level at time of entry
TARGET:      Previous VWAP high of the day
INVALIDATION: Price fails to hold VWAP for 2 consecutive bars
```

---

## Tech Stack — Free Only

| Layer | Tool | Version | Install |
|-------|------|---------|---------|
| Language | Python | 3.11+ | — |
| Market data live | alpaca-py | latest | pip |
| Market data historical | yfinance | latest | pip |
| Technical indicators | pandas-ta | latest | pip |
| Technical indicators | TA-Lib | latest | pip + system lib |
| Backtesting | vectorbt | latest | pip |
| Database | duckdb | latest | pip |
| LLM reasoning | anthropic | latest | pip |
| News sentiment | transformers + torch | latest | pip |
| Reddit sentiment | praw | latest | pip |
| Scheduling | apscheduler | latest | pip |
| Environment | python-dotenv | latest | pip |
| HTTP | httpx | latest | pip |
| Data | pandas + numpy | latest | pip |
| Alerts | discord-webhook | latest | pip |

---

## API Keys Required

All keys go in `.env` file. Never hardcode. Never commit to git.

```bash
# .env — copy from .env.example and fill in
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_FEED=iex
```

---

## Code Standards — Non-Negotiable

Follow these in every session without exception:

1. **Type hints on every function** — `def fetch_bars(ticker: str, limit: int) -> pd.DataFrame:`
2. **Write the test before the implementation** — test file first, then make it pass
3. **Log to file AND console** — use Python `logging` module, log to `logs/signal_brain.log`
4. **One function does one thing** — no functions longer than 30 lines
5. **Ask before adding libraries** — do not install anything not in `requirements.txt` without flagging it
6. **Never hardcode API keys** — always read from environment variables via `python-dotenv`
7. **Handle errors gracefully** — no bare `except:` clauses, log all errors with context
8. **No classes where functions will do** — keep it simple
9. **Every module has a docstring** — explaining what it does, what it needs, what it returns
10. **Market hours guard** — all live data functions check `is_market_open()` before running

---

## Validation Rules — How We Know If It Works

### Backtest Requirements
- Minimum 2 years historical data
- No look-ahead bias
- Separate training and test periods
- Simulated costs: $0.65/contract + $0.02/share slippage + spread estimate
- Compare against buy-and-hold SPY baseline

### Paper Trading Success Metrics
| Metric | Minimum to Continue | Target |
|--------|--------------------|----|
| Win Rate | > 45% | > 55% |
| Avg Win / Avg Loss | > 1.5x | > 2.0x |
| Expected Value | > $0 after costs | > $50/signal |
| Profit Factor | > 1.2 | > 1.5 |
| Max Drawdown | < 30% | < 20% |
| Sample Size | 100 signals minimum | 200+ |

---

## Quick Reference — Key Commands

```bash
# Install all dependencies
pip install -r requirements.txt

# Run the main scanner
python main.py

# Run tests
pytest tests/ -v

# Query the signal database
python -c "
import duckdb
conn = duckdb.connect('signal_brain.duckdb')
print(conn.execute(\"SELECT * FROM bars WHERE ticker='AAPL' ORDER BY timestamp DESC LIMIT 10\").df())
"

# Check if market is open
python -c "from feeds.market_data import is_market_open; print(is_market_open())"
```

---

## How to Start Each Session

1. Read this file from the top
2. Check which session number we are on
3. Read only that session's goal and deliverable
4. Build only what that session requires
5. Run the success test before declaring the session complete
6. Do not start the next session's work

---

## When In Doubt

- Build the simplest thing that satisfies the session goal
- Prefer functions over classes
- Prefer explicit over clever
- Log everything
- Test everything
- Ask before expanding scope

The goal is not impressive code. The goal is a working signal that we can measure.

---

*Signal Brain — CLAUDE.md — v1.0 — May 2026*
*Read this file at the start of every session. It is the source of truth.*
