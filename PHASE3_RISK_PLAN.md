# Phase 3: Risk Management Improvements — Plan

## Issues Addressed
- #16: STALE_POSITION_HOURS (24→10)
- #26: Earnings calendar filter (new module)
- #28: Adaptive position sizing (win rate multiplier)
- #30: Profit lock after daily target
- #34: STOP_LOSS_PCT (0.03→0.045)
- #36: DAILY_LOSS_LIMIT_PCT (0.20→0.08)

## Tasks Created
1. Config defaults fix (settings.py) — 3 constant changes
2. Adaptive position sizing (risk_mgr.py + position_mgr.py) — win rate multiplier
3. Profit lock (main.py) — tighter stops + smaller sizes after target
4. Earnings filter (new earnings_filter.py + main.py integration)

## Design Principles
- Fail-open: all new checks return safe defaults on failure
- No schema changes: uses existing trades table
- Config values remain live-editable via DB overrides
- Hysteresis on profit lock (90% threshold)
