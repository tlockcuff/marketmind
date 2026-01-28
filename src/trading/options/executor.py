"""Options order execution via Alpaca."""

import logging
from dataclasses import dataclass
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    LimitOrderRequest,
    MarketOrderRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class OptionsOrderResult:
    success: bool
    order_id: Optional[str] = None
    status: str = ""
    message: str = ""
    filled_price: Optional[float] = None


class OptionsExecutor:
    def __init__(self, trading_client: TradingClient):
        self.client = trading_client

    def buy_option(
        self, symbol: str, qty: int, limit_price: float
    ) -> OptionsOrderResult:
        """Buy to open an option contract."""
        try:
            request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_price, 2),
            )
            order = self.client.submit_order(request)
            logger.info(f"BTO {qty}x {symbol} @ ${limit_price:.2f}")
            return OptionsOrderResult(
                success=True,
                order_id=str(order.id),
                status=str(order.status),
                message="Buy to open submitted",
            )
        except Exception as e:
            logger.error(f"BTO failed {symbol}: {e}")
            return OptionsOrderResult(success=False, message=str(e))

    def sell_option(
        self, symbol: str, qty: int, limit_price: float
    ) -> OptionsOrderResult:
        """Sell to open (for covered calls, short legs)."""
        try:
            request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_price, 2),
            )
            order = self.client.submit_order(request)
            logger.info(f"STO {qty}x {symbol} @ ${limit_price:.2f}")
            return OptionsOrderResult(
                success=True,
                order_id=str(order.id),
                status=str(order.status),
                message="Sell to open submitted",
            )
        except Exception as e:
            logger.error(f"STO failed {symbol}: {e}")
            return OptionsOrderResult(success=False, message=str(e))

    def close_option_position(self, symbol: str) -> OptionsOrderResult:
        """Close an option position at market."""
        try:
            order = self.client.close_position(symbol)
            logger.info(f"Closing option position: {symbol}")
            return OptionsOrderResult(
                success=True,
                order_id=str(order.id) if hasattr(order, "id") else None,
                status="closing",
                message="Option close submitted",
            )
        except Exception as e:
            err_str = str(e)
            # "position not found" means Alpaca already closed/liquidated it
            if "position not found" in err_str.lower() or "40410000" in err_str:
                logger.warning(f"Position already gone on Alpaca: {symbol}")
                return OptionsOrderResult(
                    success=True,
                    status="already_closed",
                    message=f"Position not found on Alpaca (already liquidated): {symbol}",
                )
            logger.error(f"Close option failed {symbol}: {e}")
            return OptionsOrderResult(success=False, message=err_str)

    def submit_credit_spread(
        self,
        short_symbol: str,
        long_symbol: str,
        qty: int,
        credit: float,
    ) -> OptionsOrderResult:
        """Submit credit spread as multi-leg order."""
        try:
            # Alpaca multi-leg: submit as two separate orders
            # (MLEG support varies; fallback to individual legs)
            short_result = self.sell_option(short_symbol, qty, credit)
            if not short_result.success:
                return short_result

            # Buy the long leg (protection)
            # Long leg price ~ short price - net credit
            long_result = self.buy_option(long_symbol, qty, 0.01)  # market-like limit
            if not long_result.success:
                # Try to close the short leg if long fails
                logger.error("Long leg failed, closing short leg")
                self.close_option_position(short_symbol)
                return long_result

            logger.info(
                f"Credit spread: short {short_symbol} / long {long_symbol}, "
                f"{qty}x, credit=${credit:.2f}"
            )
            return OptionsOrderResult(
                success=True,
                order_id=short_result.order_id,
                status="spread_submitted",
                message=f"Credit spread submitted: {qty}x ${credit:.2f} credit",
            )
        except Exception as e:
            logger.error(f"Credit spread failed: {e}")
            return OptionsOrderResult(success=False, message=str(e))

    def close_spread(
        self, short_symbol: str, long_symbol: str, qty: int
    ) -> OptionsOrderResult:
        """Close a spread by closing both legs."""
        try:
            # Close short leg (buy to close)
            short_result = self.close_option_position(short_symbol)
            # Close long leg (sell to close)
            long_result = self.close_option_position(long_symbol)

            success = short_result.success or long_result.success
            return OptionsOrderResult(
                success=success,
                order_id=short_result.order_id,
                status="spread_closing",
                message="Spread close submitted",
            )
        except Exception as e:
            logger.error(f"Close spread failed: {e}")
            return OptionsOrderResult(success=False, message=str(e))
