# 🧠 Marketmind

An autonomous trading bot that thinks before it trades. Grok AI spots opportunities, technical analysis keeps it honest, and Alpaca pulls the trigger.

```
🤖 Grok AI  →  📡 Parse Signals  →  📊 15+ Indicators  →  📈 90-Day Backtest  →  💯 Score 0-100  →  ⚡ Execute
```

Every 5 minutes, Marketmind asks Grok for 25-30 trade ideas across all sectors, then runs each one through a gauntlet: RSI, MACD, Bollinger Bands, VWAP, volume analysis, a 90-day backtest, and a risk/reward check. Only signals scoring 50+ out of 100 get executed. Everything else gets logged so you can study what it passed on.

It trades stocks with bracket orders (automatic stop-loss and take-profit), scales out of winners gradually, and can run options strategies too — directional calls/puts, credit spreads, and covered calls on existing positions.

A live web dashboard shows everything in real-time, and Discord pings you when something happens.

![Marketmind Dashboard](docs/screenshot.png)

### ✨ Features

- 🤖 **AI signal generation** — Grok scans 25-30 ideas per cycle across every sector
- 📊 **Technical validation** — RSI, MACD, Bollinger Bands, VWAP, ATR, OBV, Stochastic, SMA/EMA
- 📈 **90-day backtesting** — every signal tested against recent history before execution
- 🧮 **Multi-factor scoring** — weighted composite of AI confidence, technicals, backtest, volume, risk/reward
- 🎯 **Bracket orders** — automatic stop-loss and take-profit on every entry
- 📐 **ATR-based trailing stops** — dynamically tighten as price moves in your favor
- 💰 **Partial profit-taking** — scale out at +3% and +6% to lock in gains
- ⚖️ **Score-tiered sizing** — higher conviction = bigger position, volatile stocks = smaller
- 🌦️ **Market regime detection** — adapts thresholds and sizing for trending, choppy, or volatile conditions
- 🏗️ **Sector concentration limits** — max 3 positions per sector to avoid overexposure
- 📜 **Options trading** — directional calls/puts, credit spreads, and covered calls
- 🔍 **AI portfolio review** — Grok re-evaluates open positions and recommends holds, exits, or stop adjustments
- 🛑 **Daily loss halt** — automatically stops trading at 20% daily drawdown
- 🔒 **PDT compliance** — tracks day trades and enforces the pattern day trader rule
- ⏰ **Time-based exits** — force close after 24h, tighten to breakeven on stale positions
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
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install
```

### 2. 🔑 Get your API keys

You need two services: **Alpaca** (executes trades) and **Grok** (generates signals).

```bash
cp .env.example .env
```

Then fill in `.env` — see the setup guides below.

### 3. 🏁 Start paper trading

**Development** — runs bot, API, and web dashboard concurrently:
```bash
npm run dev
```
Then open [http://localhost:5000](http://localhost:5000) in your browser.

**Production** — via Docker Compose:
```bash
docker compose up -d
```
Runs bot, API (:2323), and web (:5000) in containers with auto-restart. Requires an external PostgreSQL instance — set `DATABASE_URL` in `.env`.

### PostgreSQL

All trade history, API usage, config overrides, and logs are stored in an external PostgreSQL database. Schema is auto-created on first startup via `init_db()`.

Set the connection string in `.env`:
```
DATABASE_URL=postgresql://trader:trader@your-db-host:5432/daytrading
```

---

## 🦙 Alpaca Setup

[Alpaca](https://alpaca.markets) is the brokerage — it holds the account, executes orders, and reports positions. You don't need to deposit money to paper trade.

1. Sign up at [alpaca.markets](https://alpaca.markets)
2. From the dashboard, go to **Paper Trading**
3. Click **View** under API Keys, then **Generate New Key**
4. Enter your keys in the **Account Management** panel in the web dashboard

Keys are stored in the database and can be updated on the fly from the web UI. When you reset your paper account on Alpaca (which gives you new keys), just paste them into the dashboard and it will wipe all trading data automatically.

**Going live (optional):** Complete Alpaca's brokerage application, get approved, fund your account, then generate live API keys under **Live Trading** and enter them via the dashboard.

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

Marketmind uses `grok-4-1-fast-reasoning`.


---

## 📰 Finhub Setup (Optional)

[Finhub](https://finhub.io) is the news provider — it provides news articles for the dashboard to use

1. Sign up at [finhub.io](https://finhub.io)
2. From the dashboard, go to **API Keys**
3. Click **Generate New Key**
4. Paste the key into your `.env`:

```
FINNHUB_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
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
