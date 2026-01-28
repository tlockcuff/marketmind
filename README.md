# 🧠 Marketmind

An autonomous trading bot that thinks before it trades. Grok AI spots opportunities, technical analysis keeps it honest, and Alpaca pulls the trigger.

```
🤖 Grok AI  →  📡 Parse Signals  →  📊 15+ Indicators  →  📈 90-Day Backtest  →  💯 Score 0-100  →  ⚡ Execute
```

Every 5 minutes, Marketmind asks Grok for 15-20 trade ideas across all sectors, then runs each one through a gauntlet: RSI, MACD, Bollinger Bands, VWAP, volume analysis, a 90-day backtest, and a risk/reward check. Only signals scoring 65+ out of 100 get executed. Everything else gets logged so you can study what it passed on.

It trades stocks with bracket orders (automatic stop-loss and take-profit), scales out of winners gradually, and can run options strategies too — directional calls/puts, credit spreads, and covered calls on existing positions.

A live terminal dashboard shows everything in real-time, and Discord pings you when something happens.

### ✨ Features

- 🤖 **AI signal generation** — Grok scans 15-20 ideas per cycle across every sector
- 📊 **Technical validation** — RSI, MACD, Bollinger Bands, VWAP, ATR, OBV, Stochastic, SMA/EMA
- 📈 **90-day backtesting** — every signal tested against recent history before execution
- 🧮 **Multi-factor scoring** — weighted composite of AI confidence, technicals, backtest, volume, risk/reward
- 🎯 **Bracket orders** — automatic stop-loss and take-profit on every entry
- 📐 **ATR-based trailing stops** — dynamically tighten as price moves in your favor
- 💰 **Partial profit-taking** — scale out at +5%, +8%, and +12% to lock in gains
- ⚖️ **Score-tiered sizing** — higher conviction = bigger position, volatile stocks = smaller
- 🌦️ **Market regime detection** — adapts thresholds and sizing for trending, choppy, or volatile conditions
- 🏗️ **Sector concentration limits** — max 3 positions per sector to avoid overexposure
- 📜 **Options trading** — directional calls/puts, credit spreads, and covered calls
- 🔍 **AI portfolio review** — Grok re-evaluates open positions and recommends holds, exits, or stop adjustments
- 🛑 **Daily loss halt** — automatically stops trading at 10% daily drawdown
- 🔒 **PDT compliance** — tracks day trades and enforces the pattern day trader rule
- ⏰ **Time-based exits** — force close after 48h, tighten to breakeven after 24h
- 🖥️ **Live terminal dashboard** — Rich TUI with positions, P/L, orders, logs, and API usage
- 🔔 **Discord alerts** — real-time notifications for trades, closes, summaries, and halts
- 📉 **Performance analytics** — breakdowns by score, sector, exit reason, time of day, and hold time
- 📝 **Rejected signal logging** — track what you passed on and why
- 🧪 **Paper and live modes** — practice risk-free, go live when ready
- 💵 **API cost tracking** — monitor Grok usage and spending per day and all-time

---

## 📚 Documentation

- 📊 [Technical Indicators](docs/technical-indicators.md) — RSI, MACD, Bollinger Bands, and 6 more explained in plain English
- 💯 [Scoring System](docs/scoring-system.md) — How the 5 weighted components produce a 0-100 trade score
- 🛡️ [Risk Management](docs/risk-management.md) — Position limits, stop-losses, PDT rules, and market regime filters
- 📈 [Backtesting](docs/backtesting.md) — How signals are validated against 90 days of history
- 🏛️ [Congress Trading](docs/congress_trading.md) — How STOCK Act filings feed into signal generation

---

## 🚀 Quick Start

### 1. Install

```bash
git clone <repo-url> && cd day-trading
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 🔑 Get your API keys

You need two services: **Alpaca** (executes trades) and **Grok** (generates signals). Both have free tiers.

```bash
cp .env.example .env
```

Then fill in `.env` — see the setup guides below.

### 3. 🏁 Start paper trading

```bash
./watch.sh
```

This opens a full-screen terminal UI and auto-starts the bot in the background.

That's it. The bot starts in paper mode (fake money) by default. No real money is at risk until you explicitly run `./run.sh --live` and type a confirmation.

---

## 🦙 Alpaca Setup

[Alpaca](https://alpaca.markets) is the brokerage — it holds the account, executes orders, and reports positions. You don't need to deposit money to paper trade.

1. Sign up at [alpaca.markets](https://alpaca.markets)
2. From the dashboard, go to **Paper Trading**
3. Click **View** under API Keys, then **Generate New Key**
4. Paste both values into your `.env`:

```
ALPACA_PAPER_API_KEY=PKxxxxxxxxxxxxxxxx
ALPACA_PAPER_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Going live (optional):** Complete Alpaca's brokerage application, get approved, fund your account, then generate live API keys under **Live Trading** and add them:

```
ALPACA_LIVE_API_KEY=AKxxxxxxxxxxxxxxxx
ALPACA_LIVE_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Live mode requires `./run.sh --live` and typing `YES I UNDERSTAND` at the prompt.

> ⚠️ Accounts under $25k are subject to the Pattern Day Trader rule (3 day trades per 5 rolling days). Marketmind tracks and enforces this automatically so you don't get flagged.

---

## 🧠 Grok Setup

[Grok](https://console.x.ai) is the AI brain — it scans the market, generates trade ideas, and reviews your portfolio. It runs on X.ai's API.

1. Go to [console.x.ai](https://console.x.ai)
2. Create an account and generate an API key
3. Add it to `.env`:

```
GROK_API_KEY=xai-xxxxxxxxxxxxxxxxxxxxxxxx
```

Marketmind uses `grok-4-1-fast-reasoning`. You can check how much you're spending anytime:

```bash
./run.sh --usage
```

---

## 🔔 Discord Alerts (Optional)

Get pinged on your phone when trades happen.

1. In your Discord server: **Server Settings** → **Integrations** → **Webhooks** → **New Webhook**
2. Copy the URL into `.env`:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

You'll get alerts for: 🟢 new trades, 🔴 closed positions (with P/L), 📊 daily summaries, and 🛑 loss-limit halts.

---

## ⚙️ What It Does

🔍 **Finds trades** — Grok scans all sectors (tech, healthcare, energy, defense, space, nuclear, etc.) for momentum plays, breakouts, volume surges, earnings reactions, and news catalysts.

✅ **Validates everything** — Each signal gets checked against RSI, MACD, Bollinger Bands, VWAP, ATR, OBV, Stochastic, moving averages, and a 90-day backtest. A weighted score combines AI confidence, technical alignment, backtest results, volume, and risk/reward.

📏 **Sizes positions carefully** — Higher scores get bigger positions. High-volatility stocks get smaller ones. If the market regime is choppy or volatile, sizing shrinks further.

🛡️ **Manages risk automatically** — Bracket orders set stop-loss and take-profit at entry. Trailing stops (ATR-based) ratchet up as price moves in your favor. Sector limits prevent overconcentration. A daily loss limit halts all trading if things go sideways.

💰 **Scales out of winners** — At +5%, sells a third and moves stop to breakeven. At +8%, sells half of what's left and locks in profit. The rest rides a trailing stop or exits at +12%.

📜 **Trades options too** — Directional calls/puts for high-conviction plays, credit spreads for range-bound setups, and covered calls to collect premium on large stock positions.

🔄 **Reviews its own portfolio** — Every cycle, Grok re-evaluates open positions and can recommend holds, exits, or stop adjustments.

📝 **Logs everything** — Full trade history with AI rationale, score breakdowns, and sector tags. Rejected signals get logged too, so you can analyze what you're missing.

---

## 🧰 Commands

```bash
./run.sh                # 📄 Paper trading (default)
./run.sh --live         # 🔴 Live trading (requires confirmation)
./run.sh --debug        # 🐛 Verbose logging
./run.sh --status       # 📊 Market status + account info
./run.sh --usage        # 💵 Grok API cost summary

./watch.sh              # 🖥️ Live dashboard (auto-starts bot)
./watch_dev.sh          # 🔧 Dashboard with hot-reload for dev

python scripts/analyze.py             # 📈 Performance report
python scripts/analyze.py --csv out.csv  # 📤 Export to CSV

pytest tests/           # 🧪 Run tests
```

---

## 🎛️ Tuning

All parameters live in `config/settings.py`:

| Setting | Default | What it controls |
|---------|---------|------------------|
| `MAX_POSITION_PCT` | 15% | 💼 Biggest single position as % of equity |
| `MAX_CONCURRENT_POSITIONS` | 20 | 📊 Total open stock positions |
| `STOP_LOSS_PCT` | 5% | 🛑 Default stop loss distance |
| `TAKE_PROFIT_PCT` | 12% | 🎯 Default take profit target |
| `DAILY_LOSS_LIMIT_PCT` | 10% | 🚨 Halt trading at this daily drawdown |
| `MIN_SCORE_THRESHOLD` | 65 | 💯 Minimum score to execute a trade |
| `SCAN_INTERVAL_MINUTES` | 5 | ⏱️ Minutes between Grok scans |
| `OPTIONS_ENABLED` | true | 📜 Toggle options trading |
| `OPTIONS_MAX_POSITION_PCT` | 2% | 📜 Max equity per options trade |

🏗️ Sector concentration is capped at 3 positions per sector (configurable in `config/sectors.py`).

---

## 📁 Project Layout

```
config/              ⚙️ Settings, holidays, sector map, logging
src/main.py          🤖 Bot core — trading loop, signal evaluation, execution
src/signals/         📡 Grok client, signal parser, API usage tracking
src/analysis/        📊 Indicators, backtester, scorer, market data
src/trading/         💹 Alpaca client, position mgmt, risk mgmt, trade history
src/trading/options/ 📜 Contract selection, execution, sizing, position mgmt
src/notifications/   🔔 Discord webhooks
src/scheduler/       🕐 Market hours, holidays, early closes
src/dashboard.py     🖥️ Rich terminal UI
scripts/             📈 Performance analytics
tests/               🧪 Unit tests
logs/                📝 Trade history, rejected signals, API usage, session logs
```
