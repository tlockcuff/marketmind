# MarketMind Wealth Optimization Report

## Executive Summary

After thorough analysis of every source file in the codebase, I've identified **43 specific issues and improvements** organized by impact level. The highest-impact items relate to: money-losing exit logic bugs, overly passive scoring thresholds that get bypassed anyway, market data latency causing stale entries, missing News Sentinel integration in the main loop, and significant edge in smarter position sizing.

---

## CRITICAL ISSUES (Direct Money Losers)

### 1. News Sentinel Is Built But Never Started
**File:** `src/main.py` — `TradingBot.__init__()` and `_trading_cycle()`
**Problem:** The `NewsSentinel` class (`src/signals/news_sentinel.py`) is a fully-built real-time headline monitor with emergency exit, trim, and stop-tightening capabilities. However, it is **never instantiated or started** in `TradingBot.__init__()`, and `drain_actions()` is never called in `_trading_cycle()`. This means:
- Critical news (FDA rejections, SEC charges, fraud, halts) goes undetected
- The bot holds through catastrophic events that destroy position value
- Protective actions like emergency exits and stop tightening never trigger

**Fix:** Initialize `NewsSentinel` in `__init__`, call `.start()` in `run()`, and call `drain_actions()` at the start of each `_trading_cycle()` to process queued protective actions.

**Estimated Impact:** Preventing even one catastrophic loss from a fraud/halt/FDA rejection on a 25% position could save 5-25% of portfolio.

### 2. Regime-Based Score Threshold Override Defeats the Scoring System
**File:** `src/main.py`, lines 691-698
**Problem:** The market regime logic lowers `score_threshold` to 45 for `high_volatility`, `trending_down`, AND `trending_up` — that's **every regime except choppy**. Since the default threshold is already 50, this means in most market conditions the bot trades with barely any quality filter. A score of 45 means the weighted average of all signals is below neutral.

**Fix:** Differentiate more carefully:
- `trending_up`: Lower to 45 for BUY signals only, keep 55 for SELL
- `trending_down`: Lower to 45 for SELL/SHORT only, keep 55 for BUY
- `high_volatility`: RAISE to 55-60 (vol = danger for low-conviction trades)
- `choppy`: RAISE to 55 (mean-reversion only)

### 3. Position Size Multiplier in `scorer.py` Is Dead Code
**File:** `src/analysis/scorer.py`, `get_position_size_multiplier()` (lines 199-211)
**Problem:** This function returns 0.0 for scores below 65, but the actual position sizing in `position_mgr.py` (`get_position_size()`) uses its own score-based multiplier that allows trades down to score 50. The `get_position_size_multiplier()` function is **never called** anywhere.

### 4. yfinance `get_current_price()` Is Slow and Often Stale
**File:** `src/analysis/market_data.py`, `get_current_price()` (line 104-111)
**Problem:** Uses `yf.Ticker(ticker).info` which makes a full web scrape — often 1-3 seconds per call, and the price can be 15+ minutes delayed. This is called during:
- `_check_positions()` for every position (N API calls per cycle)
- `_review_portfolio()` for every position exit
- `_evaluate_signal()` for quotes

For a bot with 30 positions, this means 30+ slow API calls (60-90 seconds) just checking exits.

**Fix:** Use Alpaca's real-time snapshot API (`get_stock_snapshot`) for current positions — it supports batch requests for up to 50 symbols in a single call.

### 5. Backtest Uses Settings Constants Instead of `settings.get()`
**File:** `src/analysis/backtester.py`, line 38-39
**Problem:** Uses the raw module constant (bypassing config overrides from the DB). If you adjust stop_loss_pct or take_profit_pct via the web UI, the backtest still uses old hardcoded values.

---

## HIGH-IMPACT IMPROVEMENTS (Significant Revenue Gains)

### 6. No Slippage Model — Market Orders at Stale Prices
**File:** `src/trading/position_mgr.py`, `open_position()` line 143-149
**Problem:** Bracket orders use market orders for entry, but the `entry_price` recorded is the price at evaluation time (from yfinance, potentially minutes old). Stop and take-profit levels are calculated from stale price, not actual fill.

**Fix:** After order submission, poll for actual filled price and recalculate stop/take-profit from the real fill price.

### 7. Scale-Out Logic Has a Quantum Problem
**File:** `src/trading/position_mgr.py`, `check_exits()` lines 266-293
**Problem:** After partial close, `bracket_active` is set to False — remaining position only has stop-loss order (no take-profit). Bot relies on 5-minute check cycle to detect TP hits. Fast-moving stock can hit TP and reverse before next check.

**Fix:** After partial close, submit a new bracket order (stop + limit) for remaining shares, not just a stop order.

### 8. 5-Minute Scan Interval Is Too Slow for Day Trading
**Fix:** Implement tiered approach:
- Full Grok scan every 5 minutes
- Momentum screener + position monitoring every 1-2 minutes
- Critical exit checks (stops, scale-outs) every 30-60 seconds

### 9. Avoiding First AND Last 15 Minutes Misses Prime Trading
**File:** `src/scheduler/trading_hours.py`, `should_avoid_trading()`
**Problem:** The first and last 15 minutes are the **highest volume and highest momentum** periods.

**Fix:** Nuanced approach:
- First 5 min (9:30-9:35): Avoid NEW entries only
- 9:35-9:45: Allow high-score entries (75+) only
- Last 15 min: Allow exits/trims but no new entries

### 10. No Correlation/Correlation Matrix for Portfolio Risk
**Fix:** Implement beta-weighted exposure metric. Track net market exposure and prefer counter-cyclical trades when unbalanced.

### 11. No Time-of-Day Awareness in Signal Generation
**Fix:** Include time context in Grok prompt. Add "lunch hour" mode (12-2 PM) that reduces sizing and raises thresholds.

### 12. Momentum Screener Volume Estimation Is Unreliable
**File:** `src/signals/momentum_screener.py`, lines 105-106
**Problem:** Extrapolating single minute volume * 390 minutes is wildly inaccurate.

### 13. Momentum Screener Buys Into Gaps — Classic Retail Trap
**Problem:** For gap-up stocks, screener sets direction="buy" at current price. Over 60% of gaps fill within the first hour.

**Fix:** Add gap-and-go vs gap-and-fade criteria (volume ratio, VWAP position, candle patterns).

---

## MEDIUM-IMPACT IMPROVEMENTS

### 14. No Bid-Ask Spread Awareness for Entry
**Fix:** For stocks with spread >0.3%, use limit orders at mid-price instead of market orders.

### 15. No End-of-Day Position Review
**Fix:** Add EOD sweep at 3:50 PM ET — close weak positions, tighten stops on survivors.

### 16. Covered Call Logic Only Writes on Profitable Positions
**Fix:** Write covered calls on flat/slightly losing positions too (down <3%, held >1 day).

### 17. Credit Spread Execution Is Non-Atomic
**File:** `src/trading/options/executor.py`
**Problem:** Two separate orders (sell short leg, buy long leg) — risk of naked short option if long leg fails.

### 18. Options Directional Max Hold of 5 Days Is Too Long for 0DTE
**Fix:** Scale max hold by DTE: 0DTE close by 3:30 PM, 1-3 DTE max 1 day, 4-7 DTE max 2 days.

### 19. Bollinger Band Scoring Bug
**File:** `src/analysis/indicators.py`, `get_technical_alignment_score()`
**Problem:** Uses `bollinger_middle` position instead of current price for %B calculation. Middle band is always ~50%, contributing zero useful information.

**Fix:** Add current_price to IndicatorResult and use it for %B calculation.

### 20. No Maximum Drawdown Circuit Breaker (Intraday)
**Fix:** Rely on Alpaca bracket stops for real-time protection. Ensure replacement stops after partial close are always GTC.

### 21. Recovery Mode Should Spare Near-TP Positions
**Fix:** If position is >80% of the way to take-profit, reduce close priority.

### 22. No Adaptive Position Sizing Based on Recent Performance
**Fix:** Track rolling 10-trade win rate. Reduce sizing during losing streaks.

### 23. Market Context Fetching Uses 8+ Slow yfinance Calls
**Fix:** Use Alpaca's batch snapshot API for all market context symbols in a single call.

### 24. No Profit Lock After Big Winners
**Fix:** After scale-out Level 2 (+6%), tighten trailing stop to 1x ATR (instead of 1.5x).

---

## FEATURE SUGGESTIONS (New Revenue Sources)

### 25. Pre-Market/After-Hours Trading
Extended hours for high-conviction plays (score 75+) using limit orders only.

### 26. Sector Rotation Strategy
Track sector ETF momentum, overweight strong sectors in signal filtering.

### 27. Earnings Calendar Integration
Avoid pre-earnings entries (risk), target post-earnings momentum plays.

### 28. Signal Deduplication Across Cycles
Cache rejected signals with TTL (15-30 min). Skip re-evaluation unless new data.

### 29. Win Rate Tracking Per Signal Source
Track hit rate per source (Grok vs momentum screener). Weight by historical performance.

### 30. Chandelier Exit Trailing Stop
Implement 3x ATR from highest high since entry — superior for trend following.

### 31. VWAP-Aware Entries
Prefer entries at/below VWAP for buys, at/above VWAP for sells.

### 32. Multi-Strategy Approach
Add: Mean Reversion, Breakout, Pairs Trading, VWAP Reversion strategies.

### 33. Dynamic Stop-Loss Based on VIX Regime
Scale stops by VIX level: VIX <15 tighten, VIX >25 widen.

---

## CONFIGURATION OPTIMIZATIONS

### 34. MAX_POSITION_PCT = 0.25 Is Very Aggressive
**Recommendation:** Reduce to 10-15% per position.

### 35. DAILY_LOSS_LIMIT_PCT = 0.20 Is Extreme
**Recommendation:** Reduce to 5-8%. Professional desks use 2-5%.

### 36. STOP_LOSS_PCT = 0.03 May Be Too Tight for Volatile Stocks
**Recommendation:** Make ATR-based the primary method. Fall back to percentage only if ATR unavailable.

### 37. OPTIONS_STOP_LOSS_DIRECTIONAL = 0.50 Is Too Generous
**Recommendation:** Reduce to 30-35%.

### 38. OPTIONS_DTE_MIN = 0 (0DTE) Is Very High Risk
**Recommendation:** Require score 80+ for 0DTE, auto-close by 3:00 PM, reduce position size to 2.5%.

---

## CODE QUALITY ISSUES AFFECTING PROFITABILITY

### 39. Multiple Alpaca Client Instantiations
**Fix:** Pass a single AlpacaClient instance to all components.

### 40. No Rate Limiting on yfinance Calls
**Fix:** Implement rate limiter or batch all yfinance calls.

### 41. `get_db()` Connection Per Call
**Fix:** Use a connection pool.

### 42. Ticker Blacklist Persists for Entire Bot Lifetime
**Fix:** TTL-based blacklist that expires entries after 30-60 minutes.

### 43. No Warmup / Backfill on Restart
**Fix:** Persist position metadata (entry_time, scale_out_level, etc.) in DB and restore on restart.

---

## PRIORITY IMPLEMENTATION ORDER

### Tier 1 — Fix Money Losers (Do First)
1. #1 — Integrate News Sentinel into main loop
2. #19 — Fix Bollinger Band scoring bug
3. #6 — Track actual fill prices for stop/target calculation
4. #4 — Switch to Alpaca snapshots for current prices
5. #2 — Fix regime-based threshold logic

### Tier 2 — Increase Win Rate
6. #9 — Allow trading in opening/closing windows for high-score signals
7. #8 — Reduce scan interval / tiered monitoring
8. #11 — Time-of-day aware signal generation
9. #7 — Fix scale-out to maintain bracket protection
10. #13 — Add gap-and-go vs gap-and-fade logic

### Tier 3 — Risk Management
11. #35 — Reduce daily loss limit to 5-8%
12. #34 — Reduce max position size to 10-15%
13. #22 — Adaptive position sizing based on recent performance
14. #10 — Portfolio correlation monitoring
15. #33 — Dynamic stops by VIX regime

### Tier 4 — New Features
16. #25 — Pre-market/after-hours trading
17. #27 — Earnings calendar integration
18. #32 — Multi-strategy approach
19. #26 — Sector rotation strategy
20. #28 — Signal deduplication cache
