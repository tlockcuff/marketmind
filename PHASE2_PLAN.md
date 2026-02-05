# Phase 2: Speed & Reliability — Implementation Plan

## Problem Statement

The trading cycle makes ~140+ sequential yfinance API calls per 5-minute cycle:
- 10 positions x 1 get_current_price() call each = 10 calls
- 9 market context calls (SPY, QQQ, VIX, 6 sector ETFs)
- 20 signals x 5-6 API calls each = 100-120 calls

This causes cycles to take 15-20 minutes instead of 5, making prices stale.

## Task Breakdown

### Task 2A: Batch Alpaca Snapshots + Retry + Caching (Foundation)
- File: src/analysis/market_data.py
- retry_api_call decorator, get_batch_prices(), get_batch_quotes()
- Cache get_market_context() and get_market_regime() for 5 minutes

### Task 2B: Batch Prices in Position Checks + Rejected Signal Cache
- File: src/main.py
- Replace sequential _check_positions() with get_batch_prices()
- Add _rejected_cache with 30-minute TTL

### Task 2C: Batch Quotes in Signal Eval + Pre-filtering
- File: src/main.py
- _pre_filter_signals() method, batch-prefetch quotes

### Task 2D: Parallel Signal Evaluation
- File: src/main.py
- ThreadPoolExecutor(max_workers=4) for concurrent signal evaluation

### Task 2E: Retry in AlpacaClient + Clear Blacklist
- Files: src/trading/alpaca_client.py, src/main.py
- Retry on read-only Alpaca methods, clear blacklist each cycle

## Expected Impact
- API calls per cycle: ~140+ -> ~30-40
- Cycle time: 15-20 min -> 3-5 min
- Market context: cached 5 min
- Rejected signals: cached 30 min
- Transient failures: auto-retry + clear
