"""Database wipe endpoint for paper account resets."""

import os
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/api/reset")
async def reset_data():
    """Wipe all database data for the current trading mode.
    Used when resetting the paper trading account."""
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    if mode != "paper":
        raise HTTPException(status_code=403, detail="Reset only allowed in paper mode")

    from src.db import wipe_data
    from src.trading.trade_history import get_trade_history

    wipe_data(mode="paper")

    # Reset in-memory caches
    try:
        history = get_trade_history()
        history.trades.clear()
        history.closed_trades.clear()
    except Exception:
        pass

    return {"status": "ok", "message": "All paper trading data wiped"}
