import logging
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from config import settings
from config.sectors import MAX_PER_SECTOR
from src.trading.alpaca_client import AlpacaClient

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    qty: float
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    direction: str
    score: float
    order_id: Optional[str] = None
    atr: Optional[float] = None
    trailing_stop_updates: int = 0
    sector: Optional[str] = None
    scale_out_level: int = 0
    original_qty: Optional[float] = None
    bracket_active: bool = True


@dataclass
class PositionManager:
    alpaca: AlpacaClient = field(default_factory=AlpacaClient)
    positions: dict = field(default_factory=dict)  # symbol -> Position

    def __post_init__(self):
        self._sync_positions()

    def _sync_positions(self):
        """Sync with Alpaca positions."""
        alpaca_positions = self.alpaca.get_positions()
        for p in alpaca_positions:
            if p["symbol"] not in self.positions:
                # Position exists in Alpaca but not tracked locally
                self.positions[p["symbol"]] = Position(
                    symbol=p["symbol"],
                    qty=p["qty"],
                    entry_price=p["avg_entry"],
                    entry_time=datetime.now(),
                    stop_loss=p["avg_entry"] * (1 - settings.get("stop_loss_pct")),
                    take_profit=p["avg_entry"] * (1 + settings.get("take_profit_pct")),
                    direction="buy" if p["qty"] > 0 else "sell",
                    score=0,
                )

    def can_open_position(self) -> bool:
        """Check if we can open new position."""
        return len(self.positions) < settings.get("max_concurrent_positions")

    def can_open_in_sector(self, sector: str) -> tuple[bool, str]:
        """Check sector concentration limit."""
        if not sector or sector == "Unknown":
            return True, "OK"
        count = sum(1 for p in self.positions.values() if getattr(p, "sector", None) == sector)
        if count >= MAX_PER_SECTOR:
            return False, f"Sector {sector} full ({count}/{MAX_PER_SECTOR})"
        return True, "OK"

    def get_position_size(
        self,
        price: float,
        score: float,
        atr: float = None,
    ) -> int:
        """Calculate position size based on score, volatility, and settings."""
        account = self.alpaca.get_account()
        if not account:
            return 0

        equity = account.get("equity", 0)

        # Base position size
        max_position_value = equity * settings.get("max_position_pct")

        # Adjust based on score — aggressive sizing
        if score >= 80:
            multiplier = 1.0  # full size for top signals
        elif score >= 65:
            multiplier = 0.8
        elif score >= 50:
            multiplier = 0.6
        else:
            return 0

        # Volatility adjustment via ATR
        if atr and price > 0:
            atr_pct = atr / price
            if atr_pct > 0.05:
                multiplier *= 0.40  # very volatile
            elif atr_pct > 0.03:
                multiplier *= 0.60
            elif atr_pct > 0.02:
                multiplier *= 0.80
            # else: full size (stable)

        # Win rate adjustment (adaptive position sizing based on recent performance)
        try:
            from src.trading.risk_mgr import RiskManager
            wr_multiplier = RiskManager().get_win_rate_multiplier()
            multiplier *= wr_multiplier
        except Exception:
            pass  # Fail silently, continue with current multiplier

        position_value = max_position_value * multiplier

        # Cap to available buying power (leave 10% buffer)
        buying_power = account.get("buying_power", 0)
        bp_cap = buying_power * 0.90
        if position_value > bp_cap:
            logger.info(f"BP cap: ${position_value:,.0f} -> ${bp_cap:,.0f} (BP=${buying_power:,.0f})")
            position_value = bp_cap

        shares = int(position_value / price)

        return max(1, shares) if shares > 0 else 0

    def open_position(
        self,
        symbol: str,
        qty: int,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        score: float,
        use_bracket: bool = True,
        atr: float = None,
        sector: str = None,
    ) -> bool:
        """Open a new position."""
        if not self.can_open_position():
            logger.warning(f"Max positions reached, cannot open {symbol}")
            return False

        if symbol in self.positions:
            logger.warning(f"Already have position in {symbol}")
            return False

        if use_bracket:
            result = self.alpaca.submit_bracket_order(
                symbol=symbol,
                qty=qty,
                side=direction,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        else:
            result = self.alpaca.submit_market_order(
                symbol=symbol,
                qty=qty,
                side=direction,
            )

        if result.success:
            self.positions[symbol] = Position(
                symbol=symbol,
                qty=qty,
                entry_price=entry_price,
                entry_time=datetime.now(),
                stop_loss=stop_loss,
                take_profit=take_profit,
                direction=direction,
                score=score,
                order_id=result.order_id,
                atr=atr,
                sector=sector,
                original_qty=qty,
            )
            logger.info(f"Opened position: {symbol} {direction} {qty} @ ~{entry_price}")
            return True
        else:
            logger.error(f"Failed to open position: {result.message}")
            return False

    def close_position(self, symbol: str, reason: str = "") -> bool:
        """Close a position."""
        if symbol not in self.positions:
            logger.warning(f"No position to close for {symbol}")
            return False

        result = self.alpaca.close_position(symbol)
        if result.success:
            pos = self.positions.pop(symbol)
            logger.info(f"Closed position: {symbol} (reason: {reason})")
            return True
        else:
            logger.error(f"Failed to close {symbol}: {result.message}")
            return False

    def _partial_close(self, symbol: str, sell_qty: int, reason: str) -> bool:
        """Sell part of a position. Cancels bracket, self-manages SL for remainder."""
        pos = self.positions.get(symbol)
        if not pos or sell_qty <= 0:
            return False

        # Cancel bracket orders first (atomic — can't partially modify)
        if pos.bracket_active:
            self.alpaca.cancel_orders_for_symbol(symbol)
            import time
            time.sleep(0.5)
            pos.bracket_active = False

        # Market sell the partial qty
        sell_side = "sell" if pos.direction in ("buy", "long") else "buy"
        result = self.alpaca.submit_market_order(symbol=symbol, qty=sell_qty, side=sell_side)
        if not result.success:
            logger.error(f"Partial close failed for {symbol}: {result.message}")
            return False

        pos.qty -= sell_qty
        logger.info(f"Partial close {symbol}: sold {sell_qty}, remaining {pos.qty} ({reason})")

        # Submit stop-loss only for remaining shares
        if pos.qty > 0:
            from alpaca.trading.requests import StopOrderRequest
            from alpaca.trading.enums import OrderSide as OS, TimeInForce as TIF
            order_side = OS.SELL if sell_side == "sell" else OS.BUY
            try:
                stop_req = StopOrderRequest(
                    symbol=symbol,
                    qty=pos.qty,
                    side=order_side,
                    time_in_force=TIF.GTC,
                    stop_price=pos.stop_loss,
                )
                self.alpaca.client.submit_order(stop_req)
            except Exception as e:
                logger.warning(f"Failed to submit SL for {symbol} remainder: {e}")

        return True

    def check_exits(self, current_prices: dict) -> List[str]:
        """Check all positions for exit conditions. Returns closed symbols."""
        closed = []
        now = datetime.now()

        for symbol, pos in list(self.positions.items()):
            price = current_prices.get(symbol)
            if not price:
                continue

            held_hours = (now - pos.entry_time).total_seconds() / 3600
            should_close = False
            reason = ""

            # Time-based: force close after MAX_HOLD_HOURS
            if held_hours > settings.get("max_hold_hours"):
                should_close = True
                reason = f"max_hold_{held_hours:.0f}h"
                logger.info(f"{symbol} held {held_hours:.0f}h > {settings.get('max_hold_hours')}h, force closing")

            # Time-based: tighten stop to breakeven+0.5% after STALE_POSITION_HOURS
            elif held_hours > settings.get("stale_position_hours"):
                breakeven_stop = pos.entry_price * (1.005 if pos.direction == "buy" else 0.995)
                if pos.direction == "buy" and pos.stop_loss < breakeven_stop:
                    logger.info(f"{symbol} stale ({held_hours:.0f}h), tightening stop to breakeven+0.5%: {breakeven_stop:.2f}")
                    self.update_stop_loss(symbol, breakeven_stop)
                elif pos.direction != "buy" and pos.stop_loss > breakeven_stop:
                    logger.info(f"{symbol} stale ({held_hours:.0f}h), tightening stop to breakeven+0.5%: {breakeven_stop:.2f}")
                    self.update_stop_loss(symbol, breakeven_stop)

            # Scale-out logic (before full exit checks)
            if not should_close and pos.qty > 1:
                if pos.direction in ("buy", "long"):
                    gain_pct = (price - pos.entry_price) / pos.entry_price
                else:
                    gain_pct = (pos.entry_price - price) / pos.entry_price
                orig_qty = pos.original_qty or pos.qty

                # Level 1: +3% → sell 25%, move stop to breakeven
                if pos.scale_out_level == 0 and gain_pct >= 0.03:
                    sell_qty = max(1, int(orig_qty * 0.25))
                    if sell_qty < pos.qty:
                        if self._partial_close(symbol, sell_qty, "scale_out_3pct"):
                            pos.scale_out_level = 1
                            self.update_stop_loss(symbol, pos.entry_price)
                            logger.info(f"{symbol} scale-out L1: sold {sell_qty}, stop→breakeven")

                # Level 2: +6% → sell another 25% of original, tighten trail
                elif pos.scale_out_level == 1 and gain_pct >= 0.06:
                    sell_qty = max(1, int(orig_qty * 0.25))
                    if sell_qty < pos.qty:
                        if self._partial_close(symbol, sell_qty, "scale_out_6pct"):
                            pos.scale_out_level = 2
                            lock_stop = pos.entry_price * (1.03 if pos.direction in ("buy", "long") else 0.97)
                            self.update_stop_loss(symbol, lock_stop)
                            logger.info(f"{symbol} scale-out L2: sold {sell_qty}, stop→+3%")

                # Level 3: remainder rides trailing stop — no forced close
                # (trailing stop in _check_positions handles final exit)

            # Price-based exits
            if not should_close:
                if pos.direction in ("buy", "long"):
                    if price <= pos.stop_loss:
                        should_close = True
                        reason = "stop_loss"
                    elif price >= pos.take_profit and pos.scale_out_level == 0:
                        should_close = True
                        reason = "take_profit"
                else:  # sell/short
                    if price >= pos.stop_loss:
                        should_close = True
                        reason = "stop_loss"
                    elif price <= pos.take_profit:
                        should_close = True
                        reason = "take_profit"

            if should_close:
                if self.close_position(symbol, reason):
                    closed.append(symbol)

        return closed

    def get_daily_pnl(self) -> float:
        """Calculate total unrealized P/L for today."""
        total = 0
        for p in self.alpaca.get_positions():
            total += p["unrealized_pl"]
        return total

    def get_positions_summary(self) -> List[dict]:
        """Get summary of all positions."""
        return self.alpaca.get_positions()

    def update_stop_loss(self, symbol: str, new_stop: float) -> bool:
        """Update stop loss for trailing stop (local + Alpaca orders)."""
        if symbol not in self.positions:
            return False
        pos = self.positions[symbol]
        old_stop = pos.stop_loss
        new_stop = round(new_stop, 2)
        pos.stop_loss = new_stop

        # Replace bracket orders on Alpaca (submits fresh SL/TP regardless of existing orders)
        success = self.alpaca.replace_bracket_orders(
            symbol=symbol,
            qty=pos.qty,
            side=pos.direction,
            new_stop=new_stop,
            new_tp=pos.take_profit,
        )
        if not success:
            logger.warning(f"Failed to update Alpaca orders for {symbol}, local stop updated {old_stop:.2f}->{new_stop:.2f}")
        return True
