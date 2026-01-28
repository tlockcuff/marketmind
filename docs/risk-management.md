# 🛡️ Risk Management

Risk management is how the bot protects your money. Even a great trade idea can go wrong, so the bot uses multiple safety nets to limit losses.

---

## 📏 Position Limits

| Rule | Default | What It Does |
|------|---------|-------------|
| 💼 Max per trade | 10% of account | No single stock can use more than 10% of your money |
| 📊 Max open trades | 20 | Limits how many stocks you hold at once |
| 🚨 Daily loss limit | 10% of account | If losses for the day hit 10%, the bot stops trading |

---

## 🎯 Stop-Loss and Take-Profit

Every trade is placed as a **bracket order** — three orders in one:

1. ⬆️ **Entry** — Buy the stock
2. 🛑 **Stop-loss** — Automatically sell if the price drops too far (default: 3% below entry)
3. 🎯 **Take-profit** — Automatically sell if the price hits your target (default: 8% above entry)

The bot uses **ATR** (Average True Range) to adjust these levels. For volatile stocks, stops are set wider so normal price swings don't trigger a premature exit.

💡 **Analogy:** It's like setting a safety net below a tightrope walker. You want the net close enough to catch a fall, but not so close that normal wobbling triggers it.

---

## 🔒 Day Trade Protection (PDT Rule)

The "Pattern Day Trader" rule says accounts under $25,000 can only make 3 day trades in a 5-day window. The bot enforces this:

| Rule | Value |
|------|-------|
| 📅 Day trade limit | 3 per 5 days |
| 💯 Min score for day trade | 80 (only the best setups) |
| 🔄 Reserved day trades | 1 (kept for emergencies) |

A "day trade" means buying and selling the same stock on the same day. The bot is extra selective about these because they're a limited resource.

---

## 🌦️ Market Regime Filter

The bot checks overall market conditions before trading:

- 🔴 **VIX > 30** (high fear index): Raises the score threshold to 75 and reduces position sizes
- 📉 **SPY trending down** with a buy signal: Raises threshold to 70 (buying against the market is riskier)
- 🟢 **Normal conditions**: Standard threshold of 65

This prevents the bot from aggressively buying during market-wide selloffs.

---

## 🏗️ Sector Concentration

The bot checks whether it already has too many positions in the same industry sector. This prevents a scenario where one piece of bad sector news (e.g., new regulations on tech) wipes out multiple positions at once.
