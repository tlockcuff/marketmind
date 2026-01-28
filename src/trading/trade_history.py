"""Track trade history with rationale."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List

logger = logging.getLogger(__name__)


def get_history_file() -> Path:
    """Get mode-specific trade history file."""
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    prefix = "live" if mode == "live" else "paper"
    return Path(__file__).parent.parent.parent / "logs" / f"{prefix}_trade_history.json"


def get_rejected_file() -> Path:
    """Get mode-specific rejected signals file."""
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    prefix = "live" if mode == "live" else "paper"
    return Path(__file__).parent.parent.parent / "logs" / f"{prefix}_rejected_signals.jsonl"


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
    status: str = "open"  # open, closed, stopped_out, take_profit
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    pnl: Optional[float] = None
    asset_type: str = "stock"  # "stock" or "option"
    option_details: Optional[dict] = None
    sector: Optional[str] = None
    atr_at_entry: Optional[float] = None
    trailing_stop_updates: int = 0
    scale_out_level: int = 0


class TradeHistory:
    def __init__(self):
        self.trades: dict = {}  # symbol -> TradeRecord (for open trades)
        self.closed_trades: List[dict] = []
        self.history_file = get_history_file()
        self._load()

    def _load(self):
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text())
                self.trades = data.get("open", {})
                self.closed_trades = data.get("closed", [])
            except:
                pass

    def _save(self):
        try:
            self.history_file.parent.mkdir(exist_ok=True)
            data = {
                "open": self.trades,
                "closed": self.closed_trades,
                "updated": datetime.now().isoformat(),
            }
            self.history_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save trade history: {e}")

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
    ):
        """Record a new trade."""
        record = TradeRecord(
            symbol=symbol,
            direction=direction,
            qty=qty,
            entry_price=entry_price,
            entry_time=datetime.now().isoformat(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            score=score,
            grok_rationale=grok_rationale,
            score_breakdown=score_breakdown,
            sector=sector,
            atr_at_entry=atr_at_entry,
        )
        self.trades[symbol] = asdict(record)
        self._save()
        logger.info(f"Recorded trade: {symbol} {direction} - {grok_rationale[:50]}...")

    def record_close(
        self,
        symbol: str,
        exit_price: float,
        reason: str,
    ):
        """Record trade close."""
        if symbol not in self.trades:
            return

        trade = self.trades.pop(symbol)
        trade["status"] = reason
        trade["exit_price"] = exit_price
        trade["exit_time"] = datetime.now().isoformat()

        # Calculate P/L
        if trade["direction"] == "buy":
            trade["pnl"] = (exit_price - trade["entry_price"]) * trade["qty"]
        else:
            trade["pnl"] = (trade["entry_price"] - exit_price) * trade["qty"]

        self.closed_trades.append(trade)
        self._save()

    def record_rejected(
        self,
        symbol: str,
        direction: str,
        score: float,
        reason: str,
        score_breakdown: dict = None,
        sector: str = None,
    ):
        """Append a rejected signal to JSONL log."""
        try:
            entry = {
                "symbol": symbol,
                "direction": direction,
                "score": score,
                "reason": reason,
                "score_breakdown": score_breakdown or {},
                "sector": sector,
                "timestamp": datetime.now().isoformat(),
            }
            path = get_rejected_file()
            path.parent.mkdir(exist_ok=True)
            with open(path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"Failed to record rejected signal: {e}")

    def get_rationale(self, symbol: str) -> Optional[str]:
        """Get rationale for an open position."""
        if symbol in self.trades:
            return self.trades[symbol].get("grok_rationale", "")
        return None

    def get_trade_info(self, symbol: str) -> Optional[dict]:
        """Get full trade info for a symbol."""
        return self.trades.get(symbol)

    def get_open_trades(self) -> dict:
        """Get all open trades with rationale."""
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
        record = TradeRecord(
            symbol=symbol,
            direction=strategy,
            qty=qty,
            entry_price=entry_price,
            entry_time=datetime.now().isoformat(),
            stop_loss=0,
            take_profit=0,
            score=score,
            grok_rationale=rationale,
            score_breakdown={},
            asset_type="option",
            option_details=option_details,
        )
        self.trades[symbol] = asdict(record)
        self._save()
        logger.info(f"Recorded option trade: {symbol} {strategy}")

    def record_option_close(self, symbol: str, exit_price: float, reason: str):
        """Record options trade close."""
        if symbol not in self.trades:
            return
        trade = self.trades.pop(symbol)
        trade["status"] = reason
        trade["exit_price"] = exit_price
        trade["exit_time"] = datetime.now().isoformat()
        # P/L for options: (exit - entry) * qty * 100
        trade["pnl"] = (exit_price - trade["entry_price"]) * trade["qty"] * 100
        self.closed_trades.append(trade)
        self._save()

    def get_today_stats(self) -> dict:
        """Get today's closed trade stats."""
        today = datetime.now().date().isoformat()
        today_trades = [
            t for t in self.closed_trades
            if t.get("exit_time", "").startswith(today)
        ]

        if not today_trades:
            return {"trades": 0, "pnl": 0, "winners": 0, "losers": 0}

        pnl = sum(t.get("pnl", 0) for t in today_trades)
        winners = sum(1 for t in today_trades if t.get("pnl", 0) > 0)

        return {
            "trades": len(today_trades),
            "pnl": pnl,
            "winners": winners,
            "losers": len(today_trades) - winners,
        }


# Global instance
_history: Optional[TradeHistory] = None


def get_trade_history() -> TradeHistory:
    global _history
    if _history is None:
        _history = TradeHistory()
    return _history
