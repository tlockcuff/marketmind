"""Alpaca API key management — update keys in DB and reset data on change."""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class AlpacaKeysRequest(BaseModel):
    api_key: str
    secret_key: str
    reset_data: bool = True  # wipe DB on key change (new account)


def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return key[:4] + "..." + key[-4:]


@router.get("/api/keys")
async def get_keys():
    """Return masked Alpaca keys for display."""
    from config import settings
    settings._resolve_alpaca_keys()
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    return {
        "mode": mode,
        "api_key": _mask(settings.ALPACA_API_KEY or ""),
        "secret_key": _mask(settings.ALPACA_SECRET_KEY or ""),
    }


@router.post("/api/keys")
async def update_keys(body: AlpacaKeysRequest):
    """Update Alpaca API keys in DB. Optionally wipe data for new account."""
    import config.settings as cfg
    mode = os.environ.get("TRADING_MODE", "paper").lower()

    if not body.api_key or not body.secret_key:
        raise HTTPException(status_code=400, detail="Both api_key and secret_key required")

    # Save to DB
    from src.db import get_db
    with get_db() as conn:
        conn.execute(
            """INSERT INTO alpaca_keys (id, mode, api_key, secret_key, updated_at)
               VALUES (1, %s, %s, %s, NOW())
               ON CONFLICT (id) DO UPDATE
               SET mode = EXCLUDED.mode, api_key = EXCLUDED.api_key,
                   secret_key = EXCLUDED.secret_key, updated_at = NOW()""",
            (mode, body.api_key, body.secret_key),
        )
        conn.commit()

    # Update in-memory settings
    cfg.ALPACA_API_KEY = body.api_key
    cfg.ALPACA_SECRET_KEY = body.secret_key
    if mode == "live":
        cfg.ALPACA_LIVE_API_KEY = body.api_key
        cfg.ALPACA_LIVE_SECRET_KEY = body.secret_key
    else:
        cfg.ALPACA_PAPER_API_KEY = body.api_key
        cfg.ALPACA_PAPER_SECRET_KEY = body.secret_key

    # Reset singleton Alpaca client so it reconnects with new keys
    import api.data_provider as dp
    dp._alpaca = None
    dp._data_client = None

    from src.trading.alpaca_client import AlpacaClient
    AlpacaClient._symbol_cache = None

    # Wipe DB if requested (new account = fresh start)
    if body.reset_data:
        from src.db import wipe_data
        from src.trading.trade_history import get_trade_history
        wipe_data(mode=mode if mode != "live" else None)
        try:
            history = get_trade_history()
            history.trades.clear()
            history.closed_trades.clear()
        except Exception:
            pass

    return {
        "status": "ok",
        "mode": mode,
        "api_key": _mask(body.api_key),
        "data_reset": body.reset_data,
    }
