# 📊 Technical Indicators

This app uses 9 technical indicators to decide whether a trade is worth taking. Think of each indicator as a different "lens" 🔍 for looking at a stock's price and volume history. No single indicator is perfect, so the bot combines them all into a single score.

---

## 📉 RSI (Relative Strength Index)

**What it measures:** Whether a stock has been bought too aggressively or sold too aggressively in recent days.

**How it works:** RSI looks at the last 14 days of price changes and produces a number from 0 to 100.

- 🟢 **Below 30** = "Oversold" — the stock has been beaten down and may be due for a bounce. Good time to buy.
- 🔴 **Above 70** = "Overbought" — the stock has been bid up heavily and may be due for a pullback. Risky time to buy.
- 🟡 **30-70** = Neutral territory.

💡 **Analogy:** Imagine a rubber band being stretched. The further it's pulled in one direction, the more likely it snaps back. RSI measures how "stretched" the price is.

**Bot usage:** Adds up to +15 points for deeply oversold stocks (buy signal) or subtracts up to -15 points for overbought stocks.

---

## 📈 MACD (Moving Average Convergence Divergence)

**What it measures:** Whether a stock's momentum is speeding up or slowing down.

**How it works:** MACD compares two moving averages — a fast one (12-day) and a slow one (26-day). When the fast average pulls ahead of the slow one, momentum is building. When it falls behind, momentum is fading.

The key output is the **histogram** — a bar chart showing the gap between the MACD line and its signal line:
- 🟢 **Positive histogram** = Bullish momentum (price trend gaining strength)
- 🔴 **Negative histogram** = Bearish momentum (price trend losing strength)

💡 **Analogy:** Think of two runners 🏃 on a track. If the faster runner is pulling further ahead, that's strong momentum. If the slower runner is catching up, momentum is fading.

**Bot usage:** Adds up to +15 points when momentum supports the trade direction.

---

## 📏 SMA (Simple Moving Average)

**What it measures:** The average price over a set number of days, smoothing out daily noise.

**How it works:** The bot tracks two SMAs:
- 📅 **SMA-20** (20-day average) — short-term trend
- 📅 **SMA-50** (50-day average) — medium-term trend

If the current price is **above** these averages, the stock is in an uptrend ⬆️. If it's **below**, it's in a downtrend ⬇️.

💡 **Analogy:** If your running pace today is faster than your 20-day average, you're trending faster. If it's also faster than your 50-day average, that's an even stronger sign of improvement.

**Bot usage:** +5 points for each SMA the price is on the "right side" of (up to +10 total for a buy signal above both averages).

---

## 📐 EMA (Exponential Moving Average)

**What it measures:** Similar to SMA, but gives more weight to recent days.

**How it works:** The bot uses a 9-day EMA, which reacts faster to price changes than the SMA. It's like an SMA that pays more attention to what happened this week versus last month.

💡 **Analogy:** If SMA is your overall semester grade 📋, EMA is more like your grade weighted toward recent assignments.

**Bot usage:** Tracked as a reference point but doesn't directly add to the score.

---

## 🎸 Bollinger Bands

**What it measures:** Whether the current price is unusually high or low compared to its recent range.

**How it works:** Three lines are drawn around the price:
- ⬆️ **Upper band** = 20-day average + 2 standard deviations
- ➡️ **Middle band** = 20-day average
- ⬇️ **Lower band** = 20-day average - 2 standard deviations

About 95% of price action should fall between the upper and lower bands. When price touches the lower band, the stock is relatively cheap 🟢. When it touches the upper band, it's relatively expensive 🔴.

The bot calculates **%B** — where the price sits as a percentage between the bands (0% = lower band, 100% = upper band).

💡 **Analogy:** Imagine a highway with lane markings 🛣️. Most cars stay between the lines. A car drifting to the edge of the road is likely to correct back toward the center.

**Bot usage:** Adds up to +12 points when price is near the lower band (buy signal) or subtracts up to -6 when near the upper band.

---

## ⚖️ VWAP (Volume Weighted Average Price)

**What it measures:** The "fair price" of a stock for the day, weighted by how much trading volume occurred at each price level.

**How it works:** VWAP multiplies each price by its volume, sums it all up, then divides by total volume. It tells you the average price that traders actually paid, not just the average price on the chart.

- ⬆️ **Price above VWAP** = Buyers are in control (bullish)
- ⬇️ **Price below VWAP** = Sellers are in control (bearish)

💡 **Analogy:** If you wanted to know the "real" average price of gas ⛽ in your city, you wouldn't just average all station prices equally. You'd weight each station by how many gallons it sold. VWAP does this for stock prices.

**Bot usage:** Tracked as a reference for intraday context. Not directly scored.

---

## 🌡️ ATR (Average True Range)

**What it measures:** How much a stock typically moves in a day — its volatility.

**How it works:** ATR looks at the last 14 days and calculates the average daily range (high minus low, adjusted for gaps between days). A stock with a $5 ATR moves about $5 per day on average.

💡 **Analogy:** If you're planning a road trip 🚗, ATR tells you how bumpy the road is. A smooth highway (low ATR) means predictable driving. A mountain road (high ATR) means bigger swings in either direction.

**Bot usage:** ATR is critical for risk management rather than scoring:
- 🛑 Sets **stop-loss** distance (where to cut losses)
- 🎯 Sets **take-profit** distance (where to lock in gains)
- 📏 Adjusts **position size** (smaller positions for volatile stocks)

---

## 📢 OBV (On Balance Volume)

**What it measures:** Whether money is flowing into or out of a stock.

**How it works:** OBV keeps a running total of volume. On days the stock goes up, that day's volume is added. On days it goes down, volume is subtracted. The bot then compares OBV to its 10-day average:

- 🟢 **OBV rising above its average** = Money flowing in (accumulation)
- 🔴 **OBV falling below its average** = Money flowing out (distribution)

💡 **Analogy:** Imagine a stadium 🏟️ filling up or emptying. If more people keep arriving (rising OBV), there's growing interest. If people are leaving (falling OBV), interest is fading — even if the scoreboard (price) hasn't changed yet.

**Bot usage:** +10 points when volume flow supports the trade direction.

---

## 🔄 Stochastic Oscillator

**What it measures:** Where the current price sits relative to its recent high-low range.

**How it works:** Produces a number from 0 to 100:
- 🟢 **Below 20** = Price is near the bottom of its recent range (oversold)
- 🔴 **Above 80** = Price is near the top of its recent range (overbought)

It uses two lines:
- ⚡ **%K** (fast line) = Current position in the range
- 🐢 **%D** (slow line) = 3-day average of %K

💡 **Analogy:** If a stock traded between $90 and $100 over the past 14 days and is currently at $92, it's near the bottom of its range (Stochastic ~20). It's like checking the water level 🌊 in a pool — is it near the top or bottom of its usual range?

**Bot usage:** Adds up to +12 points for oversold readings (buy signal) or subtracts up to -8 for overbought readings.
