"""Track trade history with rationale — PostgreSQL backend."""

import json
import logging
import os
from datetime import datetime
from src.utils import utcnow
from dataclasses import dataclass
from typing import Optional, List

from src.db import get_db

logger = logging.getLogger(__name__)


def classify_strategy(score_breakdown: dict, grok_rationale: str) -> str:
    """Classify trade strategy based on signal source and rationale keywords.
    
    Returns one of: momentum, mean_reversion, breakout, trend_follow, 
    news_catalyst, congress_signal, crypto_swing, other
    """
    if not isinstance(score_breakdown, dict):
        score_breakdown = {}
    
    signal_source = score_breakdown.get("signal_source", "grok").lower()
    rationale = (grok_rationale or "").lower()
    
    # Check signal source first
    if signal_source == "congress":
        return "congress_signal"
    elif signal_source == "momentum":
        return "momentum"
    elif "crypto" in signal_source or "/usd" in rationale:
        return "crypto_swing"
    
    # Check rationale keywords
    if any(word in rationale for word in ["momentum", "uptrend", "strength", "accelerat"]):
        return "momentum"
    elif any(word in rationale for word in ["oversold", "bounce", "reversal", "support", "revert"]):
        return "mean_reversion"
    elif any(word in rationale for word in ["breakout", "break out", "resistance", "breakthrough"]):
        return "breakout"
    elif any(word in rationale for word in ["trend", "follow", "direction", "pattern"]):
        return "trend_follow"
    elif any(word in rationale for word in ["news", "earnings", "announcement", "catalyst", "event"]):
        return "news_catalyst"
    else:
        return "other"


def _mode() -> str:
    return "live" if os.environ.get("TRADING_MODE", "paper").lower() == "live" else "paper"


@dataclass
class TradeRecord:
    symbol: str
    direction: str
    qty: int
    entry_price: float
    entry_time: str
    stop_loss: float
    take_profit: float
    score: float
    grok_rationale: str
    score_breakdown: dict
    status: str = "open"
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    pnl: Optional[float] = None
    asset_type: str = "stock"
    option_details: Optional[dict] = None
    sector: Optional[str] = None
    atr_at_entry: Optional[float] = None
    trailing_stop_updates: int = 0
    scale_out_level: int = 0


class TradeHistory:
    def __init__(self):
        self.trades: dict = {}  # symbol -> dict (open trades cache)
        self.closed_trades: List[dict] = []
        self._load()

    def _load(self):
        """Load open trades from DB into memory cache."""
        mode = _mode()
        try:
            with get_db() as conn:
                rows = conn.execute(
                    """SELECT symbol, direction, qty, entry_price, entry_time,
                              stop_loss, take_profit, score, grok_rationale,
                              score_breakdown, status, exit_price, exit_time, pnl,
                              asset_type, option_details, sector, atr_at_entry,
                              trailing_stop_updates, scale_out_level, hold_duration_hours,
                              strategy_tag
                       FROM trades WHERE mode = %s AND status = 'open'""",
                    (mode,),
                ).fetchall()
                self.trades = {}
                for r in rows:
                    symbol = r[0]
                    self.trades[symbol] = {
                        "symbol": r[0],
                        "direction": r[1],
                        "qty": r[2],
                        "entry_price": float(r[3]) if r[3] else 0,
                        "entry_time": r[4].isoformat() if r[4] else None,
                        "stop_loss": float(r[5]) if r[5] else 0,
                        "take_profit": float(r[6]) if r[6] else 0,
                        "score": float(r[7]) if r[7] else 0,
                        "grok_rationale": r[8] or "",
                        "score_breakdown": r[9] or {},
                        "status": r[10],
                        "exit_price": float(r[11]) if r[11] else None,
                        "exit_time": r[12].isoformat() if r[12] else None,
                        "pnl": float(r[13]) if r[13] else None,
                        "asset_type": r[14] or "stock",
                        "option_details": r[15],
                        "sector": r[16],
                        "atr_at_entry": float(r[17]) if r[17] else None,
                        "trailing_stop_updates": r[18] or 0,
                        "scale_out_level": r[19] or 0,
                        "hold_duration_hours": float(r[20]) if r[20] else None,
                        "strategy_tag": r[21] or "other",
                    }
                # Also load recent closed trades for stats
                closed_rows = conn.execute(
                    """SELECT symbol, direction, qty, entry_price, entry_time,
                              stop_loss, take_profit, score, grok_rationale,
                              score_breakdown, status, exit_price, exit_time, pnl,
                              asset_type, option_details, sector, atr_at_entry,
                              trailing_stop_updates, scale_out_level, hold_duration_hours,
                              strategy_tag
                       FROM trades WHERE mode = %s AND status != 'open'
                       ORDER BY exit_time DESC
                       LIMIT 500""",
                    (mode,),
                ).fetchall()
                self.closed_trades = []
                for r in closed_rows:
                    self.closed_trades.append({
                        "symbol": r[0],
                        "direction": r[1],
                        "qty": r[2],
                        "entry_price": float(r[3]) if r[3] else 0,
                        "entry_time": r[4].isoformat() if r[4] else None,
                        "stop_loss": float(r[5]) if r[5] else 0,
                        "take_profit": float(r[6]) if r[6] else 0,
                        "score": float(r[7]) if r[7] else 0,
                        "grok_rationale": r[8] or "",
                        "score_breakdown": r[9] or {},
                        "status": r[10],
                        "exit_price": float(r[11]) if r[11] else None,
                        "exit_time": r[12].isoformat() if r[12] else None,
                        "pnl": float(r[13]) if r[13] else None,
                        "asset_type": r[14] or "stock",
                        "option_details": r[15],
                        "sector": r[16],
                        "atr_at_entry": float(r[17]) if r[17] else None,
                        "trailing_stop_updates": r[18] or 0,
                        "scale_out_level": r[19] or 0,
                        "hold_duration_hours": float(r[20]) if r[20] else None,
                        "strategy_tag": r[21] or "other",
                    })
        except Exception as e:
            logger.warning(f"Failed to load trades from DB: {e}")

    def record_open(
        self,
        symbol: str,
        direction: str,
        qty: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        score: float,
        grok_rationale: str,
        score_breakdown: dict,
        sector: str = None,
        atr_at_entry: float = None,
        signal_source: str = "grok",
    ):
        """Record a new trade."""
        mode = _mode()
        now = utcnow()
        # Store signal_source in score_breakdown for attribution tracking
        score_breakdown_with_source = dict(score_breakdown or {})
        score_breakdown_with_source["signal_source"] = signal_source
        
        # Classify strategy based on signal source and rationale
        strategy_tag = classify_strategy(score_breakdown_with_source, grok_rationale)
        
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO trades (mode, symbol, direction, qty, entry_price,
                              entry_time, stop_loss, take_profit, score,
                              grok_rationale, score_breakdown, sector, atr_at_entry,
                              strategy_tag)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (mode, symbol, direction, qty, entry_price, now,
                     stop_loss, take_profit, score, grok_rationale,
                     json.dumps(score_breakdown_with_source), sector, atr_at_entry,
                     strategy_tag),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record trade: {e}")
            return

        # Update in-memory cache
        self.trades[symbol] = {
            "symbol": symbol, "direction": direction, "qty": qty,
            "entry_price": entry_price, "entry_time": now.isoformat(),
            "stop_loss": stop_loss, "take_profit": take_profit,
            "score": score, "grok_rationale": grok_rationale,
            "score_breakdown": score_breakdown_with_source, "status": "open",
            "sector": sector, "atr_at_entry": atr_at_entry,
            "asset_type": "stock", "opened_at": now.isoformat(),
            "trailing_stop_updates": 0, "scale_out_level": 0,
            "strategy_tag": strategy_tag,
        }
        logger.info(f"Recorded trade: {symbol} {direction} ({strategy_tag}) - {grok_rationale[:50]}...")

    def record_close(self, symbol: str, exit_price: float, reason: str):
        """Record trade close."""
        if symbol not in self.trades:
            return
        mode = _mode()
        now = utcnow()
        trade = self.trades[symbol]

        if trade["direction"] == "buy":
            pnl = (exit_price - trade["entry_price"]) * trade["qty"]
        else:
            pnl = (trade["entry_price"] - exit_price) * trade["qty"]

        # Calculate hold duration in hours
        entry_time_str = trade.get("entry_time")
        hold_duration_hours = None
        if entry_time_str:
            try:
                from datetime import datetime
                if isinstance(entry_time_str, str):
                    entry_time = datetime.fromisoformat(entry_time_str)
                else:
                    entry_time = entry_time_str
                hold_duration_hours = (now - entry_time).total_seconds() / 3600
            except Exception as e:
                logger.warning(f"Failed to calculate hold duration: {e}")

        try:
            with get_db() as conn:
                conn.execute(
                    """UPDATE trades SET status = %s, exit_price = %s,
                              exit_time = %s, pnl = %s, hold_duration_hours = %s
                       WHERE mode = %s AND symbol = %s AND status = 'open'""",
                    (reason, exit_price, now, pnl, hold_duration_hours, mode, symbol),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record close: {e}")
            return

        # Update cache
        trade["status"] = reason
        trade["exit_price"] = exit_price
        trade["exit_time"] = now.isoformat()
        trade["pnl"] = pnl
        trade["hold_duration_hours"] = hold_duration_hours
        self.trades.pop(symbol, None)
        self.closed_trades.insert(0, trade)
        # Keep in-memory closed trades bounded
        if len(self.closed_trades) > 500:
            self.closed_trades = self.closed_trades[:500]

    def record_rejected(
        self,
        symbol: str,
        direction: str,
        score: float,
        reason: str,
        score_breakdown: dict = None,
        sector: str = None,
    ):
        """Record a rejected signal."""
        mode = _mode()
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO rejected_signals (mode, symbol, direction, score,
                              reason, score_breakdown, sector)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (mode, symbol, direction, score, reason,
                     json.dumps(score_breakdown or {}), sector),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record rejected signal: {e}")

    def get_rationale(self, symbol: str) -> Optional[str]:
        if symbol in self.trades:
            return self.trades[symbol].get("grok_rationale", "")
        return None

    def get_trade_info(self, symbol: str) -> Optional[dict]:
        return self.trades.get(symbol)

    def get_open_trades(self) -> dict:
        return self.trades

    def record_option_open(
        self,
        symbol: str,
        strategy: str,
        qty: int,
        entry_price: float,
        score: float,
        rationale: str,
        option_details: dict,
    ):
        """Record an options trade open."""
        mode = _mode()
        now = utcnow()
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO trades (mode, symbol, direction, qty, entry_price,
                              entry_time, stop_loss, take_profit, score,
                              grok_rationale, score_breakdown, asset_type, option_details)
                       VALUES (%s, %s, %s, %s, %s, %s, 0, 0, %s, %s, '{}', 'option', %s)""",
                    (mode, symbol, strategy, qty, entry_price, now, score,
                     rationale, json.dumps(option_details)),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record option trade: {e}")
            return

        self.trades[symbol] = {
            "symbol": symbol, "direction": strategy, "qty": qty,
            "entry_price": entry_price, "entry_time": now.isoformat(),
            "stop_loss": 0, "take_profit": 0, "score": score,
            "grok_rationale": rationale, "score_breakdown": {},
            "status": "open", "asset_type": "option",
            "option_details": option_details,
            "trailing_stop_updates": 0, "scale_out_level": 0,
        }
        logger.info(f"Recorded option trade: {symbol} {strategy}")

    def record_option_close(self, symbol: str, exit_price: float, reason: str):
        """Record options trade close."""
        if symbol not in self.trades:
            return
        mode = _mode()
        now = utcnow()
        trade = self.trades[symbol]
        pnl = (exit_price - trade["entry_price"]) * trade["qty"] * 100

        try:
            with get_db() as conn:
                conn.execute(
                    """UPDATE trades SET status = %s, exit_price = %s,
                              exit_time = %s, pnl = %s
                       WHERE mode = %s AND symbol = %s AND status = 'open'""",
                    (reason, exit_price, now, pnl, mode, symbol),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record option close: {e}")
            return

        trade["status"] = reason
        trade["exit_price"] = exit_price
        trade["exit_time"] = now.isoformat()
        trade["pnl"] = pnl
        self.trades.pop(symbol, None)
        self.closed_trades.insert(0, trade)
        if len(self.closed_trades) > 500:
            self.closed_trades = self.closed_trades[:500]

    def get_today_stats(self) -> dict:
        """Get today's closed trade stats."""
        mode = _mode()
        today = utcnow().date()
        try:
            with get_db() as conn:
                row = conn.execute(
                    """SELECT COUNT(*), COALESCE(SUM(pnl), 0),
                              COUNT(*) FILTER (WHERE pnl > 0)
                       FROM trades
                       WHERE mode = %s AND status != 'open'
                             AND exit_time::date = %s""",
                    (mode, today),
                ).fetchone()
                trades_count, pnl, winners = row[0], float(row[1]), row[2]
                return {
                    "trades": trades_count,
                    "pnl": pnl,
                    "winners": winners,
                    "losers": trades_count - winners,
                }
        except Exception as e:
            logger.warning(f"Failed to get today stats: {e}")
            return {"trades": 0, "pnl": 0, "winners": 0, "losers": 0}


    def get_performance_stats(self, lookback_days: int = 30) -> dict:
        """Calculate win rate, profit factor, and per-source attribution stats."""
        mode = _mode()
        try:
            with get_db() as conn:
                rows = conn.execute(
                    """SELECT pnl, score_breakdown
                       FROM trades
                       WHERE mode = %s AND status != 'open' AND pnl IS NOT NULL
                             AND exit_time >= NOW() - INTERVAL '%s days'
                       ORDER BY exit_time DESC""",
                    (mode, lookback_days),
                ).fetchall()

                if not rows:
                    return {"trades": 0, "win_rate": 0, "profit_factor": 0, "by_source": {}}

                total = len(rows)
                wins = 0
                gross_profit = 0.0
                gross_loss = 0.0
                by_source: dict = {}

                for r in rows:
                    pnl = float(r[0])
                    breakdown = r[1] or {}
                    source = breakdown.get("signal_source", "unknown") if isinstance(breakdown, dict) else "unknown"

                    if pnl > 0:
                        wins += 1
                        gross_profit += pnl
                    else:
                        gross_loss += abs(pnl)

                    if source not in by_source:
                        by_source[source] = {"trades": 0, "wins": 0, "pnl": 0.0, "gross_profit": 0.0, "gross_loss": 0.0}
                    by_source[source]["trades"] += 1
                    by_source[source]["pnl"] += pnl
                    if pnl > 0:
                        by_source[source]["wins"] += 1
                        by_source[source]["gross_profit"] += pnl
                    else:
                        by_source[source]["gross_loss"] += abs(pnl)

                # Calculate per-source metrics
                for src_stats in by_source.values():
                    src_stats["win_rate"] = (src_stats["wins"] / src_stats["trades"] * 100) if src_stats["trades"] else 0
                    src_stats["profit_factor"] = (src_stats["gross_profit"] / src_stats["gross_loss"]) if src_stats["gross_loss"] > 0 else float('inf') if src_stats["gross_profit"] > 0 else 0

                profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

                return {
                    "trades": total,
                    "wins": wins,
                    "losses": total - wins,
                    "win_rate": wins / total * 100,
                    "gross_profit": gross_profit,
                    "gross_loss": gross_loss,
                    "net_pnl": gross_profit - gross_loss,
                    "profit_factor": profit_factor,
                    "by_source": by_source,
                }
        except Exception as e:
            logger.warning(f"Failed to get performance stats: {e}")
            return {"trades": 0, "win_rate": 0, "profit_factor": 0, "by_source": {}}


# Global instance
_history: Optional[TradeHistory] = None


def get_trade_history() -> TradeHistory:
    global _history
    if _history is None:
        _history = TradeHistory()
    return _history
