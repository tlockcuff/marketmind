"""Core data provider - reads same sources as the TUI dashboard."""

from __future__ import annotations

import json
import os
import sys
from collections import deque
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from src.trading.alpaca_client import AlpacaClient
from src.trading.trade_history import get_trade_history
from src.signals.usage_tracker import get_tracker
from src.scheduler.trading_hours import (
    format_market_status,
    now_et,
    is_market_open,
    time_until_open,
    time_until_close,
    MARKET_OPEN,
    MARKET_CLOSE,
    EARLY_CLOSE,
)
from config.holidays import EARLY_CLOSE_DAYS
from src.trading.options.position_mgr import _get_positions_file

# Singleton client
_alpaca: AlpacaClient | None = None


def _client() -> AlpacaClient:
    global _alpaca
    if _alpaca is None:
        _alpaca = AlpacaClient()
    return _alpaca


def _log_file() -> Path:
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    prefix = "live" if mode == "live" else "paper"
    return PROJECT_ROOT / "logs" / f"{prefix}_trading.log"


def _lock_file() -> Path:
    return PROJECT_ROOT / "logs" / "bot.lock"


def _bot_running() -> bool:
    lock = _lock_file()
    if not lock.exists():
        return False
    try:
        pid = int(lock.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_account() -> dict:
    try:
        return _client().get_account()
    except Exception as e:
        return {"error": str(e)}


def get_positions() -> list[dict]:
    try:
        positions = _client().get_positions()
        history = get_trade_history()
        history._load()  # reload from disk
        for pos in positions:
            symbol = pos.get("symbol", "")
            pos["name"] = _client().get_asset_name(symbol)
            trade = history.trades.get(symbol, {})
            pos["rationale"] = trade.get("grok_rationale", "")
            pos["score"] = trade.get("score", 0)
        return positions
    except Exception as e:
        return [{"error": str(e)}]


def get_options() -> list[dict]:
    try:
        path = _get_positions_file()
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        positions = data.get("positions", {})
        return [
            {**v, "key": k}
            for k, v in positions.items()
            if v.get("status") == "open"
        ]
    except Exception as e:
        return [{"error": str(e)}]


def get_orders() -> list[dict]:
    try:
        return _client().get_open_orders()
    except Exception as e:
        return [{"error": str(e)}]


def get_stats() -> dict:
    try:
        client = _client()
        positions = client.get_positions()
        orders = client.get_open_orders()
        account = client.get_account()
        winners = sum(1 for p in positions if p["unrealized_pl"] > 0)
        losers = len(positions) - winners
        return {
            "position_count": len(positions),
            "max_positions": settings.MAX_CONCURRENT_POSITIONS,
            "winners": winners,
            "losers": losers,
            "open_orders": len(orders),
            "day_trades_remaining": account.get("day_trades_remaining", 0),
            "day_trade_count": account.get("day_trade_count", 0),
            "is_paper": settings.is_paper_mode(),
        }
    except Exception as e:
        return {"error": str(e)}


def get_config() -> dict:
    overrides = settings.get_config_overrides()
    result = {}
    for key in settings.EDITABLE_SETTINGS:
        result[key] = settings.get(key)
    return {
        "values": result,
        "overrides": list(overrides.keys()),
        "settings_meta": settings.EDITABLE_SETTINGS,
    }


def get_api_usage() -> dict:
    try:
        tracker = get_tracker()
        return {
            "today": tracker.get_today_summary(),
            "total": tracker.get_total_summary(),
        }
    except Exception as e:
        return {"error": str(e)}


def get_logs(n: int = 100) -> list[str]:
    path = _log_file()
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            # Read from end for efficiency
            f.seek(0, 2)
            size = f.tell()
            # Read last chunk (generous estimate)
            chunk = min(size, n * 500)
            f.seek(max(0, size - chunk))
            text = f.read().decode("utf-8", errors="replace")
        lines = text.splitlines()
        return lines[-n:]
    except Exception:
        return []


def _get_market_session() -> str:
    from datetime import datetime
    now = now_et()
    t = now.time()
    if now.weekday() >= 5:
        return "Weekend"
    close = EARLY_CLOSE if now.date() in EARLY_CLOSE_DAYS else MARKET_CLOSE
    pre_market = datetime.strptime("04:00", "%H:%M").time()
    after_close = datetime.strptime("20:00", "%H:%M").time()
    if MARKET_OPEN <= t < close:
        return "Market Open"
    elif pre_market <= t < MARKET_OPEN:
        return "Pre-Market"
    elif close <= t < after_close:
        return "After Hours"
    return "Overnight"


def get_status() -> dict:
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    now = now_et()
    return {
        "market_status": format_market_status(),
        "session": _get_market_session(),
        "is_open": is_market_open(),
        "trading_mode": mode,
        "bot_running": _bot_running(),
        "current_time": now.strftime("%a %b %d %I:%M:%S %p ET"),
        "time_until_open": time_until_open(),
        "time_until_close": time_until_close(),
    }


def get_trade_history_data() -> dict:
    try:
        history = get_trade_history()
        history._load()
        return {
            "open": history.trades,
            "closed": history.closed_trades,
        }
    except Exception as e:
        return {"error": str(e)}


def get_news() -> dict:
    try:
        from api.news_provider import fetch_news
        return fetch_news()
    except Exception as e:
        return {"articles": [], "sectors": [], "error": str(e)}


def get_full_snapshot() -> dict:
    from datetime import datetime
    return {
        "account": get_account(),
        "positions": get_positions(),
        "options": get_options(),
        "orders": get_orders(),
        "stats": get_stats(),
        "config": get_config(),
        "api_usage": get_api_usage(),
        "logs": get_logs(),
        "status": get_status(),
        "history": get_trade_history_data(),
        "news": get_news(),
        "timestamp": datetime.now().isoformat(),
    }
