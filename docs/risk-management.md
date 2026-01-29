# 🛡️ Risk Management

Risk management is how the bot protects your money. Even a great trade idea can go wrong, so the bot uses multiple safety nets to limit losses.

---

## 📏 Position Limits

| Rule | Default | What It Does |
|------|---------|-------------|
| 💼 Max per trade | 25% of account | Each trade can use up to 25% of equity |
| 📊 Max open trades | 30 | Limits how many stocks you hold at once |
| 🚨 Daily loss limit | 20% of account | If losses for the day hit 20%, the bot stops trading |

---

## 🎯 Stop-Loss and Take-Profit

Every trade is placed as a **bracket order** — three orders in one:

1. ⬆️ **Entry** — Buy the stock
2. 🛑 **Stop-loss** — Automatically sell if the price drops too far (default: 3% below entry)
3. 🎯 **Take-profit** — Automatically sell if the price hits your target (default: 15% above entry)

The bot uses **ATR** (Average True Range) to adjust these levels. For volatile stocks, stops are set wider so normal price swings don't trigger a premature exit.

💡 **Analogy:** It's like setting a safety net below a tightrope walker. You want the net close enough to catch a fall, but not so close that normal wobbling triggers it.

---

## 🔒 Day Trade Protection (PDT Rule)

The "Pattern Day Trader" rule says accounts under $25,000 can only make 3 day trades in a 5-day window. The bot enforces this:

| Rule | Value |
|------|-------|
| 📅 Day trade limit | 3 per 5 days |
| 💯 Min score for day trade | 60 (more freely) |
| 🔄 Reserved day trades | 1 (kept for emergencies) |

A "day trade" means buying and selling the same stock on the same day. The bot is extra selective about these because they're a limited resource.

---

## 🌦️ Market Regime Filter

The bot checks overall market conditions — but treats volatility as opportunity, not risk:

- 🔴 **VIX > 30** (high volatility): Lowers threshold to 45 — more trades in volatile markets
- 📉 **SPY trending down**: Lowers threshold to 45 — shorts thrive here
- 📈 **SPY trending up**: Lowers threshold to 45 — ride the wave
- 🟡 **Choppy conditions**: Standard threshold of 50

Position sizes are NOT reduced in volatile regimes. High-score trades (80+) get a 1.2x oversize multiplier.

---

## 🏗️ Sector Concentration

The bot checks whether it already has too many positions in the same industry sector. This prevents a scenario where one piece of bad sector news (e.g., new regulations on tech) wipes out multiple positions at once.
