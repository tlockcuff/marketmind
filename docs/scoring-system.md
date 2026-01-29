# 💯 Scoring System

The bot combines all its analysis into a single score from 0 to 100. Think of it like a report card — each subject (component) has a weight, and the final grade determines whether a trade happens.

---

## 📊 Score Components

| Component | Weight | What It Asks |
|-----------|--------|-------------|
| 🤖 Grok AI Confidence | 20% | How confident is the AI that this is a good trade idea? |
| 📈 Technical Alignment | 30% | Do the chart indicators support this trade? |
| 📅 Backtest Performance | 20% | Has this type of setup worked in the last 90 days? |
| 📢 Volume / Momentum | 15% | Is there enough trading activity behind this move? |
| ⚖️ Risk / Reward Ratio | 15% | Is the potential gain worth the potential loss? |

---

## 🔍 Component Details

### 🤖 Grok AI Confidence (20%)

The bot queries Grok (an AI model) for trade ideas. Grok returns a confidence level from 0-100 for each idea. This is passed through directly as a raw score.

### 📈 Technical Alignment (30%)

This is where the 9 technical indicators come together. Starting from a neutral score of 50, each indicator nudges the score up or down:

| Indicator | Max Boost | Max Penalty |
|-----------|-----------|-------------|
| 📊 RSI | +15 | -15 |
| 📉 MACD | +15 | -10 |
| 📏 SMA (20 + 50) | +10 | -10 |
| 🎸 Bollinger Bands | +12 | -6 |
| 📢 OBV | +10 | 0 |
| 🔄 Stochastic | +12 | -8 |

See 📊 [Technical Indicators](technical-indicators.md) for details on each.

### 📅 Backtest Performance (20%)

The bot replays the proposed trade against the last 90 days of real price data to see how it would have performed. It scores based on:

- ✅ **Win rate** — What percentage of similar setups were profitable? (up to 30 pts)
- 💰 **Average return** — How much did winning trades make? (up to 30 pts)
- 📉 **Max drawdown** — What was the worst dip during the trade? (up to 20 pts)
- 📐 **Sharpe ratio** — How good were returns relative to risk? (up to 20 pts)

### 📢 Volume / Momentum (15%)

Compares current trading volume to the stock's average volume:

| Volume vs Average | Score |
|-------------------|-------|
| 2x or more | 🟢 100 |
| 1.5x | 🟢 80 |
| 1x (normal) | 🟡 60 |
| 0.7x | 🟠 40 |
| 0.5x | 🔴 25 |
| Below 0.5x | 🔴 10 |

📢 High volume means more traders agree with the price move, making it more reliable.

### ⚖️ Risk / Reward Ratio (15%)

Compares how much you could gain versus how much you could lose:

| Ratio | Score | Meaning |
|-------|-------|---------|
| 3:1+ | 🟢 100 | Could gain 3x what you'd lose |
| 2.5:1 | 🟢 85 | |
| 2:1 | 🟡 70 | |
| 1.5:1 | 🟡 55 | |
| 1:1 | 🟠 40 | Even odds |
| Below 1:1 | 🔴 20 | Risk exceeds reward |

---

## 🎯 Decision Thresholds

| Final Score | Action | What It Means |
|-------------|--------|---------------|
| 80+ | 🟢 Strong Buy | Everything lines up — full position (1.2x oversize) |
| 65-79 | 🟡 Buy | Good setup — 80% position |
| 50-64 | 🟠 Buy | Meets threshold — 60% position |
| Below 50 | 🔴 Skip | Not convincing enough to trade |

### 🌦️ Market Regime Adjustments

Volatility = opportunity. The threshold DROPS in active markets:

- 🟢 **Trending up**: Lowered to 45 — ride the wave
- 📉 **Trending down**: Lowered to 45 — shorts thrive
- 🔴 **High volatility** (VIX > 30): Lowered to 45 — more setups in chaos
- 🟡 **Choppy**: Standard threshold of 50

---

## 📏 Position Sizing by Score

Even when a trade passes the threshold, higher scores get bigger positions:

| Score | Position Size |
|-------|--------------|
| 80+ | 💪 100% of max allocation (1.2x oversize in execution) |
| 65-79 | 👍 80% |
| 50-64 | 👌 60% |
| Below 50 | 🚫 No trade |
