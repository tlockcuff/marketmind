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

# Set daily P/L target
./run.sh --target 1000

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
Grok AI ─────────┐
                  ├→ Signal Parser → Technical Validation → Scorer → Risk Check → Alpaca Execution
Momentum Screener┘
```

1. **GrokClient** (`src/signals/grok_client.py`) queries Grok API for 25-30 trade ideas
1b. **MomentumScreener** (`src/signals/momentum_screener.py`) independently scans Alpaca for gap plays, volume leaders
2. **SignalParser** extracts structured signals (ticker, direction, confidence, prices)
3. **MarketDataFetcher** gets historical bars (Alpaca primary, yfinance fallback)
4. **Indicators** calculate RSI, MACD, Bollinger, VWAP, ATR, etc.
5. **Backtester** validates signal against 90-day history
6. **Scorer** computes weighted score (50+ triggers trade):
   - Grok confidence: 20%
   - Technical alignment: 30%
   - Backtest performance: 20%
   - Volume/momentum: 15%
   - Risk/reward: 15%
7. **RiskManager** enforces position limits and daily loss cap
8. **AlpacaClient** executes bracket orders with stop-loss/take-profit
9. **Short selling** enabled — sell/short signals open real short positions
10. **Scale-out**: +3% sell 25% (stop→breakeven), +6% sell 25% more, remainder rides trailing stop

### Main Loop (`src/main.py`)
- PID lock prevents duplicate instances
- Respects market hours (9:30-4:00 ET) or 24/7 paper mode
- Every 5 minutes: scan Grok + momentum screener, evaluate, execute if score ≥ 50
- Monitors positions for stop/target exits + partial profit-taking
- Short signals open real short positions (not just close longs)
- Portfolio review: Grok can ADD (buy more) or TRIM (partial sell) positions
- `--target N` flag: logs daily P/L progress toward $N goal

### Dashboard (`src/dashboard.py`)
- Rich TUI showing positions, P/L, logs, API usage
- BotManager subprocess controls bot lifecycle

## Key Settings (`config/settings.py`)

| Setting | Default | Purpose |
|---------|---------|---------|
| TRADING_MODE | "paper" | "paper" or "live" |
| MAX_POSITION_PCT | 0.25 | 25% of equity per trade |
| MAX_CONCURRENT_POSITIONS | 30 | Position limit |
| STOP_LOSS_PCT | 0.03 | 3% stop loss (tight) |
| TAKE_PROFIT_PCT | 0.15 | 15% take profit |
| DAILY_LOSS_LIMIT_PCT | 0.20 | Halt at 20% daily loss |
| MIN_SCORE_THRESHOLD | 50 | Minimum score to trade |
| SCAN_INTERVAL_MINUTES | 5 | Grok query frequency |
| MIN_HOLD_MINUTES | 10 | Min hold before Grok exit |
| MAX_HOLD_HOURS | 24 | Force close after 24h |
| DAY_TRADE_LIMIT | 3 | PDT rule: 3 per 5 days |
| MIN_SCORE_FOR_DAY_TRADE | 60 | Day trade more freely |
| RESERVE_DAY_TRADES | 1 | Keep 1 for emergencies |
| DAILY_TARGET | None | Daily P/L target in $ |
| OPTIONS_DTE_MIN | 0 | 0DTE enabled |
| OPTIONS_DTE_MAX | 14 | Shorter expiries |
| OPTIONS_MAX_POSITION_PCT | 0.05 | 5% per options trade |
| OPTIONS_MAX_CONCURRENT | 20 | Options position limit |
| OPTIONS_DELTA_RANGE | (0.40, 0.70) | Wider deltas for leverage |

## Environment Variables

Required in `.env`:
- `TRADING_MODE` - "paper" (default) or "live"
- `GROK_API_KEY` - X.ai API key
- `ALPACA_PAPER_API_KEY` / `ALPACA_PAPER_SECRET_KEY` - Paper trading
- `ALPACA_LIVE_API_KEY` / `ALPACA_LIVE_SECRET_KEY` - Live trading (optional)
- `FINNHUB_API_KEY` - Finnhub API key for market news (optional)
- `DISCORD_WEBHOOK_URL` - Optional alerts

## Data Files (`logs/`)

- `bot.lock` - PID lock file
- `trade_history.json` - Open/closed trades with rationale
- `api_usage.json` - Grok API cost tracking
- `symbol_cache.json` - Cached company names
- `trading.log` - Current session (TUI reads this)
