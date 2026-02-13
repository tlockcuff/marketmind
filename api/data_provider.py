"""Core data provider - reads from PostgreSQL database."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from src.db import get_db
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
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest

# Singleton clients
_alpaca: AlpacaClient | None = None
_data_client: StockHistoricalDataClient | None = None


def _keys_configured() -> bool:
    """Check if Alpaca keys are available."""
    return bool(settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY)


def _client() -> AlpacaClient:
    global _alpaca
    if _alpaca is None:
        settings._resolve_alpaca_keys()
        if not _keys_configured():
            return None
        _alpaca = AlpacaClient()
    return _alpaca


def _data_client_() -> StockHistoricalDataClient:
    global _data_client
    if _data_client is None:
        settings._resolve_alpaca_keys()
        if not _keys_configured():
            return None
        _data_client = StockHistoricalDataClient(
            settings.ALPACA_API_KEY,
            settings.ALPACA_SECRET_KEY,
        )
    return _data_client


def _mode() -> str:
    return "live" if os.environ.get("TRADING_MODE", "paper").lower() == "live" else "paper"


def _bot_running() -> bool:
    """Check if bot is running via API BotManager or bot_instances table."""
    from api.bot_manager import get_bot_manager
    if get_bot_manager().is_running():
        return True
    try:
        with get_db() as conn:
            rows = conn.execute("SELECT pid FROM bot_instances").fetchall()
            for row in rows:
                pid = row[0]
                try:
                    os.kill(pid, 0)
                    return True
                except (ProcessLookupError, PermissionError):
                    conn.execute("DELETE FROM bot_instances WHERE pid = %s", (pid,))
                    conn.commit()
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_account() -> dict:
    try:
        c = _client()
        if c is None:
            return {"error": "Alpaca keys not configured"}
        account = c.get_account()

        # Query realized P/L from trades table (closed trades)
        mode = _mode()
        try:
            with get_db() as conn:
                result = conn.execute(
                    "SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE mode = %s AND status != 'open'",
                    (mode,)
                ).fetchone()
                account["realized_pnl"] = float(result[0]) if result else 0
        except Exception as e:
            account["realized_pnl"] = 0

        # Calculate unrealized P/L from current positions
        try:
            positions = c.get_positions()
            account["unrealized_pnl"] = sum(p.get("unrealized_pl", 0) for p in positions)
        except Exception as e:
            account["unrealized_pnl"] = 0

        # Total P/L = realized + unrealized
        account["total_pnl"] = account["realized_pnl"] + account["unrealized_pnl"]

        return account
    except Exception as e:
        return {"error": str(e)}


def get_positions() -> list[dict]:
    try:
        c = _client()
        if c is None:
            return []
        positions = c.get_positions()
        history = get_trade_history()
        history._load()  # reload from DB
        for pos in positions:
            symbol = pos.get("symbol", "")
            pos["name"] = c.get_asset_name(symbol)
            trade = history.trades.get(symbol, {})
            pos["rationale"] = trade.get("grok_rationale", "")
            pos["score"] = trade.get("score", 0)
        return positions
    except Exception as e:
        return [{"error": str(e)}]


def get_options() -> list[dict]:
    mode = _mode()
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT key, strategy, underlying, contracts, entry_time,
                          net_debit_credit, max_loss, max_profit, score,
                          profit_target_pct, stop_loss_pct, dte_exit,
                          entry_underlying_price, status
                   FROM options_positions
                   WHERE mode = %s AND status = 'open'""",
                (mode,),
            ).fetchall()
            return [
                {
                    "key": r[0], "strategy": r[1], "underlying": r[2],
                    "contracts": r[3], "entry_time": r[4].isoformat() if r[4] else "",
                    "net_debit_credit": float(r[5]) if r[5] else 0,
                    "max_loss": float(r[6]) if r[6] else 0,
                    "max_profit": float(r[7]) if r[7] else 0,
                    "score": float(r[8]) if r[8] else 0,
                    "status": r[13],
                }
                for r in rows
            ]
    except Exception as e:
        return [{"error": str(e)}]


def get_orders() -> list[dict]:
    try:
        c = _client()
        if c is None:
            return []
        return c.get_open_orders()
    except Exception as e:
        return [{"error": str(e)}]


def get_stats() -> dict:
    try:
        c = _client()
        if c is None:
            return {"error": "Alpaca keys not configured", "is_paper": settings.is_paper_mode()}
        positions = c.get_positions()
        orders = c.get_open_orders()
        account = c.get_account()
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
    """Read logs from DB."""
    from src.db_logger import get_logs as db_get_logs
    return db_get_logs(n)


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
        "keys_configured": _keys_configured(),
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


_INDEX_SYMBOLS = ["SPY", "DIA", "IWM", "QQQ"]
# SPY = S&P 500 Index
# DIA = Dow Jones Industrial Average
# IWM = Russell 2000 Index
# QQQ = Nasdaq 100 Index
# VIXY = CBOE Volatility Index (VIX) ETF
_VIX_SYMBOL = "VIXY"  # VIX ETF (Alpaca doesn't support ^VIX directly)

# Cache indices for 30s to avoid hammering API
_indices_cache: dict | None = None
_indices_cache_ts: float = 0


def get_market_indices() -> list[dict]:
    """Fetch snapshot quotes for major indices + volatility."""
    import time
    global _indices_cache, _indices_cache_ts

    now = time.time()
    if _indices_cache is not None and now - _indices_cache_ts < 30:
        return _indices_cache

    try:
        client = _data_client_()
        if client is None:
            return []
        symbols = _INDEX_SYMBOLS + [_VIX_SYMBOL]
        req = StockSnapshotRequest(symbol_or_symbols=symbols)
        snapshots = client.get_stock_snapshot(req)
        result = []
        for sym in symbols:
            snap = snapshots.get(sym)
            if not snap:
                continue
            price = snap.latest_trade.price if snap.latest_trade else 0
            prev = snap.previous_daily_bar.close if snap.previous_daily_bar else 0
            change = price - prev if prev else 0
            change_pct = (change / prev * 100) if prev else 0
            result.append({
                "symbol": sym,
                "price": round(price, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "is_vix": sym == _VIX_SYMBOL,
            })
        _indices_cache = result
        _indices_cache_ts = now
        return result
    except Exception as e:
        return []


def get_analytics_data(date_range: str = "ALL") -> dict:
    """Aggregate analytics from trades + daily_stats tables."""
    from datetime import datetime, timedelta

    mode = _mode()
    now = datetime.now()

    range_map = {
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
    }
    cutoff = now - range_map[date_range] if date_range in range_map else None

    try:
        with get_db() as conn:
            # Equity curve from daily_stats
            if cutoff:
                eq_rows = conn.execute(
                    "SELECT date, starting_equity FROM daily_stats WHERE date >= %s ORDER BY date",
                    (cutoff.date(),),
                ).fetchall()
            else:
                eq_rows = conn.execute(
                    "SELECT date, starting_equity FROM daily_stats ORDER BY date"
                ).fetchall()

            equity_curve = [
                {"date": r[0].isoformat(), "equity": float(r[1]) if r[1] else 0}
                for r in eq_rows
            ]

            # Closed trades
            q = """SELECT symbol, direction, qty, entry_price, exit_price, pnl,
                          entry_time, exit_time, sector, score
                   FROM trades WHERE mode = %s AND status != 'open'"""
            params: list = [mode]
            if cutoff:
                q += " AND exit_time >= %s"
                params.append(cutoff)
            q += " ORDER BY exit_time"
            trade_rows = conn.execute(q, params).fetchall()

            trades = []
            for r in trade_rows:
                trades.append({
                    "symbol": r[0],
                    "direction": r[1],
                    "qty": r[2],
                    "entry_price": float(r[3]) if r[3] else 0,
                    "exit_price": float(r[4]) if r[4] else 0,
                    "pnl": float(r[5]) if r[5] else 0,
                    "entry_time": r[6].isoformat() if r[6] else None,
                    "exit_time": r[7].isoformat() if r[7] else None,
                    "sector": r[8] or "Unknown",
                    "score": float(r[9]) if r[9] else 0,
                })

            # Compute metrics
            pnls = [t["pnl"] for t in trades]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]

            total_pnl = sum(pnls)
            win_count = len(wins)
            loss_count = len(losses)
            total_trades = len(pnls)
            win_rate = (win_count / total_trades * 100) if total_trades else 0
            avg_win = (sum(wins) / win_count) if wins else 0
            avg_loss = (sum(losses) / loss_count) if losses else 0
            profit_factor = (sum(wins) / abs(sum(losses))) if losses else 0
            best_trade = max(pnls) if pnls else 0
            worst_trade = min(pnls) if pnls else 0

            # Max drawdown from equity curve
            max_drawdown = 0
            peak = 0
            for pt in equity_curve:
                eq = pt["equity"]
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak * 100 if peak else 0
                if dd > max_drawdown:
                    max_drawdown = dd

            # Sharpe ratio (daily returns from equity curve)
            sharpe = 0
            if len(equity_curve) >= 2:
                returns = []
                for i in range(1, len(equity_curve)):
                    prev = equity_curve[i - 1]["equity"]
                    cur = equity_curve[i]["equity"]
                    if prev:
                        returns.append((cur - prev) / prev)
                if returns:
                    import statistics
                    mean_r = statistics.mean(returns)
                    std_r = statistics.stdev(returns) if len(returns) > 1 else 0
                    sharpe = (mean_r / std_r * (252 ** 0.5)) if std_r else 0

            # Sector breakdown
            sector_pnl: dict[str, float] = {}
            for t in trades:
                s = t["sector"]
                sector_pnl[s] = sector_pnl.get(s, 0) + t["pnl"]
            sector_breakdown = [{"sector": k, "pnl": round(v, 2)} for k, v in sector_pnl.items()]

            # Cumulative P/L series
            cumulative = []
            running = 0
            for t in trades:
                running += t["pnl"]
                cumulative.append({
                    "date": t["exit_time"],
                    "cumulative_pnl": round(running, 2),
                    "symbol": t["symbol"],
                    "pnl": t["pnl"],
                })

            return {
                "equity_curve": equity_curve,
                "trades": trades,
                "cumulative_pnl": cumulative,
                "sector_breakdown": sector_breakdown,
                "metrics": {
                    "total_pnl": round(total_pnl, 2),
                    "total_trades": total_trades,
                    "win_count": win_count,
                    "loss_count": loss_count,
                    "win_rate": round(win_rate, 1),
                    "avg_win": round(avg_win, 2),
                    "avg_loss": round(avg_loss, 2),
                    "profit_factor": round(profit_factor, 2),
                    "best_trade": round(best_trade, 2),
                    "worst_trade": round(worst_trade, 2),
                    "max_drawdown": round(max_drawdown, 2),
                    "sharpe_ratio": round(sharpe, 2),
                },
            }
    except Exception as e:
        return {"error": str(e)}


def get_crypto_positions() -> list[dict]:
    """Fetch open crypto positions from trades table with live prices."""
    mode = _mode()
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT symbol, direction, qty, entry_price, pnl, entry_time,
                          stop_loss, take_profit, score, status
                   FROM trades
                   WHERE mode = %s AND status = 'open'
                         AND (asset_type = 'crypto' OR symbol LIKE '%%/USD')""",
                (mode,),
            ).fetchall()

        if not rows:
            return []

        # Try to get live prices from Alpaca crypto snapshots
        live_prices: dict[str, float] = {}
        try:
            from alpaca.data.historical.crypto import CryptoHistoricalDataClient
            from alpaca.data.requests import CryptoSnapshotRequest

            settings._resolve_alpaca_keys()
            if _keys_configured():
                crypto_client = CryptoHistoricalDataClient(
                    settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY
                )
                symbols = [r[0] for r in rows]
                req = CryptoSnapshotRequest(symbol_or_symbols=symbols)
                snapshots = crypto_client.get_crypto_snapshot(req)
                for sym, snap in snapshots.items():
                    if snap and snap.latest_trade:
                        live_prices[sym] = float(snap.latest_trade.price)
        except Exception:
            pass

        result = []
        for r in rows:
            symbol = r[0]
            direction = r[1]
            qty = float(r[2]) if r[2] else 0
            entry_price = float(r[3]) if r[3] else 0
            current_price = live_prices.get(symbol, entry_price)
            multiplier = 1 if direction == "long" else -1
            unrealized_pl = (current_price - entry_price) * qty * multiplier
            unrealized_plpc = ((current_price - entry_price) / entry_price * multiplier) if entry_price else 0
            score = float(r[8]) if r[8] else 0

            result.append({
                "symbol": symbol,
                "qty": qty,
                "avg_entry": entry_price,
                "current_price": current_price,
                "unrealized_pl": round(unrealized_pl, 2),
                "unrealized_plpc": round(unrealized_plpc, 4),
                "score": score,
                "direction": direction or "long",
                "name": symbol,
            })

        return result
    except Exception as e:
        return []


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
        "crypto": get_crypto_positions(),
        "market_indices": get_market_indices(),
        "timestamp": datetime.now().isoformat(),
    }
