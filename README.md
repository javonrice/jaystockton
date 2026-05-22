# Signal Brain

Personal intraday stock signal platform. Watches 500–2,000 tickers during market hours, detects technical setups confirmed by volume and momentum, and delivers actionable Discord alerts.

See `CLAUDE.md` for the full architecture and session roadmap.

## Current Status: Session 1 — Data Pipeline

Polls Alpaca Markets REST API every 60 seconds for minute bars across 32 tickers (Tier 1 equities + Tier 2 sector ETFs). Stores results in DuckDB.

## Quick Start

### Option A — GitHub Codespaces (recommended)

1. Open repo in Codespaces — `requirements.txt` installs automatically
2. Add your Alpaca credentials as Codespaces secrets (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`) **or** copy `.env.example` to `.env` and fill in values
3. Run the scanner:
   ```bash
   python main.py
   ```

### Option B — Local

```bash
git clone <this-repo>
cd jaystockton
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Alpaca API key and secret
python main.py
```

## Verify It's Working

After one market-hours scan cycle, run the success query:

```bash
python -c "
import duckdb
conn = duckdb.connect('signal_brain.duckdb')
print(conn.execute(\"SELECT * FROM bars WHERE ticker='AAPL' ORDER BY timestamp DESC LIMIT 10\").df())
"
```

Expected: 10 rows with clean OHLCV data for AAPL.

## Run Tests

```bash
pytest tests/ -v
```

## Project Structure

```
signal-brain/
├── .devcontainer/       ← GitHub Codespaces config
├── feeds/               ← Alpaca data pipeline (Session 1)
├── signals/             ← Breakout + momentum detection (Session 2)
├── options/             ← Options flow analysis (Session 5)
├── fusion/              ← Multi-signal scoring engine (Session 6)
├── news/                ← FinBERT + EDGAR sentiment (Session 7)
├── alerts/              ← Discord webhook delivery (Session 7)
├── journal/             ← DuckDB logging + logger setup
├── backtest/            ← vectorbt backtesting (Session 4)
├── tests/               ← pytest test suite
├── config.py            ← All parameters (reads from .env)
└── main.py              ← Entry point
```
