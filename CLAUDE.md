# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run bot (paper trading - default)
./run.sh

# Run bot (live trading - requires confirmation)
./run.sh --live

# Run with debug logging
./run.sh --debug

# Show market status only
./run.sh --status

# Show Grok API usage stats
./run.sh --usage

# Run live dashboard (starts bot automatically)
./watch.sh

# Run dashboard with hot-reload for development
./watch_dev.sh

# Run tests
pytest tests/

# Run single test file
pytest tests/test_scorer.py -v

# Run specific test
pytest tests/test_scorer.py::test_high_score -v
```

## Architecture

### Signal Flow
```
Grok AI → Signal Parser → Technical Validation → Scorer → Risk Check → Alpaca Execution
```

1. **GrokClient** (`src/signals/grok_client.py`) queries Grok API for 15-20 trade ideas
2. **SignalParser** extracts structured signals (ticker, direction, confidence, prices)
3. **MarketDataFetcher** gets historical bars (Alpaca primary, yfinance fallback)
4. **Indicators** calculate RSI, MACD, Bollinger, VWAP, ATR, etc.
5. **Backtester** validates signal against 30-day history
6. **Scorer** computes weighted score (60+ triggers trade):
   - Grok confidence: 20%
   - Technical alignment: 30%
   - Backtest performance: 25%
   - Volume/momentum: 15%
   - Risk/reward: 10%
7. **RiskManager** enforces position limits and daily loss cap
8. **AlpacaClient** executes bracket orders with stop-loss/take-profit

### Main Loop (`src/main.py`)
- PID lock prevents duplicate instances
- Respects market hours (9:30-4:00 ET) or 24/7 paper mode
- Every 5 minutes: scan signals, evaluate, execute if score ≥ 60
- Monitors positions for stop/target exits

### Dashboard (`src/dashboard.py`)
- Rich TUI showing positions, P/L, logs, API usage
- BotManager subprocess controls bot lifecycle

## Key Settings (`config/settings.py`)

| Setting | Default | Purpose |
|---------|---------|---------|
| TRADING_MODE | "paper" | "paper" or "live" |
| MAX_POSITION_PCT | 0.10 | 10% of equity per trade |
| MAX_CONCURRENT_POSITIONS | 20 | Position limit |
| STOP_LOSS_PCT | 0.03 | 3% stop loss |
| TAKE_PROFIT_PCT | 0.08 | 8% take profit |
| DAILY_LOSS_LIMIT_PCT | 0.10 | Halt at 10% daily loss |
| MIN_SCORE_THRESHOLD | 60 | Minimum score to trade |
| SCAN_INTERVAL_MINUTES | 5 | Grok query frequency |
| DAY_TRADE_LIMIT | 3 | PDT rule: 3 per 5 days |
| MIN_SCORE_FOR_DAY_TRADE | 80 | Only day trade high-score |
| RESERVE_DAY_TRADES | 1 | Keep 1 for emergencies |

## Environment Variables

Required in `.env`:
- `TRADING_MODE` - "paper" (default) or "live"
- `GROK_API_KEY` - X.ai API key
- `ALPACA_PAPER_API_KEY` / `ALPACA_PAPER_SECRET_KEY` - Paper trading
- `ALPACA_LIVE_API_KEY` / `ALPACA_LIVE_SECRET_KEY` - Live trading (optional)
- `DISCORD_WEBHOOK_URL` - Optional alerts

## Data Files (`logs/`)

- `bot.lock` - PID lock file
- `trade_history.json` - Open/closed trades with rationale
- `api_usage.json` - Grok API cost tracking
- `symbol_cache.json` - Cached company names
- `trading.log` - Current session (TUI reads this)
