import json
import logging
import os
from datetime import datetime, date
from typing import Optional
from dataclasses import dataclass, field

from config import settings
from src.trading.alpaca_client import AlpacaClient

logger = logging.getLogger(__name__)

_DAILY_STATS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "daily_stats.json")


@dataclass
class DailyStats:
    date: date
    starting_equity: float
    trades_executed: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0
    max_drawdown: float = 0
    peak_equity: float = 0


@dataclass
class RiskManager:
    alpaca: AlpacaClient = field(default_factory=AlpacaClient)
    daily_stats: Optional[DailyStats] = None
    trading_halted: bool = False
    halt_reason: str = ""

    def __post_init__(self):
        self._init_daily_stats()

    def _init_daily_stats(self):
        """Initialize or reset daily stats. Persists starting_equity to survive restarts."""
        today = date.today()
        if self.daily_stats is None or self.daily_stats.date != today:
            account = self.alpaca.get_account()
            equity = account.get("equity", settings.PAPER_PORTFOLIO_SIZE)

            # Try to restore today's starting_equity from disk
            starting_equity = equity
            try:
                with open(_DAILY_STATS_FILE) as f:
                    saved = json.load(f)
                if saved.get("date") == str(today):
                    starting_equity = saved["starting_equity"]
                    logger.info(f"Restored starting_equity=${starting_equity:,.0f} from disk")
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                pass

            # New day or first run — persist starting_equity
            if starting_equity == equity:
                self._save_daily_stats(today, equity)

            self.daily_stats = DailyStats(
                date=today,
                starting_equity=starting_equity,
                peak_equity=max(equity, starting_equity),
            )
            self.trading_halted = False
            self.halt_reason = ""

    def _save_daily_stats(self, day: date, starting_equity: float):
        """Persist starting_equity so it survives restarts."""
        try:
            os.makedirs(os.path.dirname(_DAILY_STATS_FILE), exist_ok=True)
            with open(_DAILY_STATS_FILE, "w") as f:
                json.dump({"date": str(day), "starting_equity": starting_equity}, f)
        except Exception as e:
            logger.warning(f"Failed to save daily stats: {e}")

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed based on risk rules."""
        self._init_daily_stats()

        if self.trading_halted:
            return False, self.halt_reason

        account = self.alpaca.get_account()
        if not account:
            return False, "Cannot fetch account"

        # Check if account is blocked
        if account.get("trading_blocked") or account.get("account_blocked"):
            return False, "Account blocked by broker"

        current_equity = account.get("equity", 0)

        # Check daily loss limit
        daily_pnl = current_equity - self.daily_stats.starting_equity
        daily_loss_pct = abs(daily_pnl) / self.daily_stats.starting_equity if daily_pnl < 0 else 0

        if daily_loss_pct >= settings.DAILY_LOSS_LIMIT_PCT:
            self.trading_halted = True
            self.halt_reason = f"Daily loss limit hit: {daily_loss_pct:.1%}"
            logger.warning(self.halt_reason)
            return False, self.halt_reason

        # Check day trade limit (PDT rule for live accounts < $25k)
        day_trades_remaining = account.get("day_trades_remaining", 999)
        if day_trades_remaining <= 0:
            return False, f"Day trade limit reached (PDT rule)"

        # Update peak and drawdown
        if current_equity > self.daily_stats.peak_equity:
            self.daily_stats.peak_equity = current_equity
        drawdown = (self.daily_stats.peak_equity - current_equity) / self.daily_stats.peak_equity
        self.daily_stats.max_drawdown = max(self.daily_stats.max_drawdown, drawdown)

        # Check buying power
        if account.get("buying_power", 0) < 1000:
            return False, "Insufficient buying power"

        logger.info("Risk check passed")
        return True, "OK"

    def calculate_stop_loss(
        self,
        entry_price: float,
        direction: str,
        atr: float = None,
    ) -> float:
        """Calculate stop loss price."""
        if atr:
            # ATR-based stop (2x ATR)
            stop_distance = atr * 2
        else:
            # Percentage-based stop
            stop_distance = entry_price * settings.STOP_LOSS_PCT

        if direction in ("buy", "long"):
            return round(entry_price - stop_distance, 2)
        else:
            return round(entry_price + stop_distance, 2)

    def calculate_take_profit(
        self,
        entry_price: float,
        direction: str,
        stop_loss: float = None,
        risk_reward: float = 2.5,
    ) -> float:
        """Calculate take profit price."""
        if stop_loss:
            # Based on R:R ratio
            risk = abs(entry_price - stop_loss)
            reward = risk * risk_reward
        else:
            # Percentage-based
            reward = entry_price * settings.TAKE_PROFIT_PCT

        if direction in ("buy", "long"):
            return round(entry_price + reward, 2)
        else:
            return round(entry_price - reward, 2)

    def calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        current_stop: float,
        direction: str,
        trail_pct: float = 0.02,
        atr: float = None,
    ) -> float:
        """Calculate trailing stop. Uses ATR-based trail if atr provided."""
        if atr and current_price > 0:
            trail_pct = max(0.015, min(0.05, 1.5 * atr / current_price))

        if direction in ("buy", "long"):
            new_stop = current_price * (1 - trail_pct)
            return max(current_stop, new_stop)  # Only move up
        else:
            new_stop = current_price * (1 + trail_pct)
            return min(current_stop, new_stop)  # Only move down

    def record_trade(self, pnl: float):
        """Record a completed trade."""
        self._init_daily_stats()
        self.daily_stats.trades_executed += 1
        self.daily_stats.total_pnl += pnl
        if pnl > 0:
            self.daily_stats.wins += 1
        else:
            self.daily_stats.losses += 1

    def get_daily_summary(self) -> dict:
        """Get summary of today's trading."""
        self._init_daily_stats()
        account = self.alpaca.get_account()
        current_equity = account.get("equity", 0) if account else 0

        return {
            "date": str(self.daily_stats.date),
            "starting_equity": self.daily_stats.starting_equity,
            "current_equity": current_equity,
            "daily_pnl": current_equity - self.daily_stats.starting_equity,
            "daily_pnl_pct": (current_equity - self.daily_stats.starting_equity) / self.daily_stats.starting_equity * 100,
            "trades": self.daily_stats.trades_executed,
            "wins": self.daily_stats.wins,
            "losses": self.daily_stats.losses,
            "win_rate": self.daily_stats.wins / self.daily_stats.trades_executed * 100 if self.daily_stats.trades_executed > 0 else 0,
            "max_drawdown": self.daily_stats.max_drawdown * 100,
            "trading_halted": self.trading_halted,
            "halt_reason": self.halt_reason,
        }

    def validate_position_size(
        self,
        symbol: str,
        qty: int,
        price: float,
    ) -> tuple[bool, str, int]:
        """Validate and potentially adjust position size."""
        account = self.alpaca.get_account()
        if not account:
            return False, "Cannot fetch account", 0

        position_value = qty * price
        equity = account.get("equity", 0)
        max_position = equity * settings.MAX_POSITION_PCT

        if position_value > max_position:
            adjusted_qty = int(max_position / price)
            if adjusted_qty < 1:
                return False, "Position too small after adjustment", 0
            return True, f"Adjusted from {qty} to {adjusted_qty}", adjusted_qty

        return True, "OK", qty

    def can_day_trade(self, score: float) -> tuple[bool, str]:
        """Check if we can use a day trade (same-day exit allowed).

        For live accounts with PDT restrictions, we conserve day trades:
        - Only use for high-score trades (80+)
        - Reserve 1 day trade for emergencies
        """
        account = self.alpaca.get_account()
        if not account:
            return False, "Cannot fetch account"

        # Paper trading = unlimited
        if account.get("is_paper", False):
            return True, "Paper mode"

        day_trades_remaining = account.get("day_trades_remaining", 0)

        # Check if we have day trades available (minus reserve)
        usable_day_trades = day_trades_remaining - settings.RESERVE_DAY_TRADES
        if usable_day_trades <= 0:
            return False, f"Reserving {settings.RESERVE_DAY_TRADES} day trade(s) for emergencies"

        # Only allow day trades for high-confidence signals
        if score < settings.MIN_SCORE_FOR_DAY_TRADE:
            return False, f"Score {score:.0f} < {settings.MIN_SCORE_FOR_DAY_TRADE} (swing trade only)"

        return True, f"Day trade allowed ({usable_day_trades} available)"

    def get_trade_strategy(self, score: float) -> str:
        """Determine if this should be a day trade or swing trade."""
        can_dt, _ = self.can_day_trade(score)
        return "day_trade" if can_dt else "swing_trade"
