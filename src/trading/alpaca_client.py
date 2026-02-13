import logging
import time
import functools
from typing import Optional, List
from dataclasses import dataclass

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
    GetOrdersRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, QueryOrderStatus

from config import settings
from src.db import get_db

logger = logging.getLogger(__name__)


def _retry(max_retries=3, base_delay=1.0):
    """Decorator: retry with exponential backoff for transient API failures."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"retry {func.__name__} attempt {attempt+1} failed: {e}, retrying in {delay:.1f}s")
                        time.sleep(delay)
            logger.error(f"{func.__name__} failed after {max_retries} attempts: {last_exception}")
            raise last_exception
        return wrapper
    return decorator


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str]
    filled_price: Optional[float]
    filled_qty: Optional[float]
    status: str
    message: str


class AlpacaClient:
    # Class-level cache for symbol names (persists across instances)
    _symbol_cache: dict = None

    def __init__(self):
        self.paper = settings.is_paper_mode()
        self.client = TradingClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            paper=self.paper,
        )
        logger.info(f"Alpaca client initialized (mode={'paper' if self.paper else 'LIVE'})")
        # Load cache from DB on first init
        if AlpacaClient._symbol_cache is None:
            AlpacaClient._symbol_cache = self._load_cache()

    def _load_cache(self) -> dict:
        """Load symbol cache from DB."""
        try:
            with get_db() as conn:
                rows = conn.execute("SELECT symbol, name FROM symbol_cache").fetchall()
                return {r[0]: r[1] for r in rows}
        except Exception:
            return {}

    def _save_cache_entry(self, symbol: str, name: str):
        """Save a single symbol cache entry to DB."""
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO symbol_cache (symbol, name) VALUES (%s, %s) "
                    "ON CONFLICT (symbol) DO UPDATE SET name = EXCLUDED.name",
                    (symbol, name),
                )
                conn.commit()
        except Exception:
            pass

    def get_asset_name(self, symbol: str) -> str:
        """Get company name for symbol (cached to disk)."""
        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]

        try:
            asset = self.client.get_asset(symbol)
            # Clean up the name (remove "Common Stock", "Inc.", etc.)
            name = asset.name
            for suffix in [" Common Stock", " Class A", " Class B", " Class C",
                          ", Inc.", " Inc.", " Corp.", " Corporation",
                          " Ltd.", " Limited", " PLC", " N.V.", " S.A."]:
                name = name.replace(suffix, "")
            name = name.strip()
            # Truncate if too long
            if len(name) > 15:
                name = name[:14] + "."
            self._symbol_cache[symbol] = name
            self._save_cache_entry(symbol, name)
            return name
        except Exception as e:
            logger.debug(f"Failed to get asset name for {symbol}: {e}")
            self._symbol_cache[symbol] = symbol
            return symbol

    def get_account(self) -> dict:
        """Get account info."""
        @_retry(max_retries=3, base_delay=1.0)
        def _get_account_inner():
            account = self.client.get_account()
            equity = float(account.equity)
            day_trade_count = int(account.daytrade_count) if account.daytrade_count else 0
            is_pdt = account.pattern_day_trader

            # Calculate remaining day trades
            if self.paper:
                day_trades_remaining = 999  # Unlimited for paper
            elif is_pdt or equity >= settings.PDT_EQUITY_THRESHOLD:
                day_trades_remaining = 999  # PDT or high equity = unlimited
            else:
                day_trades_remaining = max(0, settings.DAY_TRADE_LIMIT - day_trade_count)

            last_equity = float(account.last_equity) if account.last_equity else equity
            daily_change = equity - last_equity
            daily_change_pct = (daily_change / last_equity * 100) if last_equity else 0

            return {
                "equity": equity,
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value),
                "long_market_value": float(account.long_market_value) if account.long_market_value else 0,
                "short_market_value": float(account.short_market_value) if account.short_market_value else 0,
                "last_equity": last_equity,
                "daily_change": daily_change,
                "daily_change_pct": daily_change_pct,
                "initial_margin": float(account.initial_margin) if account.initial_margin else 0,
                "maintenance_margin": float(account.maintenance_margin) if account.maintenance_margin else 0,
                "sma": float(account.sma) if account.sma else 0,
                "day_trade_count": day_trade_count,
                "day_trades_remaining": day_trades_remaining,
                "pattern_day_trader": is_pdt,
                "trading_blocked": account.trading_blocked,
                "account_blocked": account.account_blocked,
                "is_paper": self.paper,
            }

        try:
            return _get_account_inner()
        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            return {}

    def get_positions(self) -> List[dict]:
        """Get all open positions."""
        @_retry(max_retries=3, base_delay=1.0)
        def _get_positions_inner():
            positions = self.client.get_all_positions()
            return [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "side": p.side,
                    "avg_entry": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc),
                    "asset_class": getattr(p, "asset_class", "us_equity"),
                }
                for p in positions
            ]

        try:
            return _get_positions_inner()
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def get_position(self, symbol: str) -> Optional[dict]:
        """Get position for specific symbol."""
        @_retry(max_retries=3, base_delay=1.0)
        def _get_position_inner():
            p = self.client.get_open_position(symbol)
            return {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "side": p.side,
                "avg_entry": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }

        try:
            return _get_position_inner()
        except Exception:
            return None

    def submit_market_order(
        self,
        symbol: str,
        qty: float,
        side: str,
    ) -> OrderResult:
        """Submit market order."""
        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            # Crypto requires GTC; stocks use DAY
            is_crypto = "/" in symbol or symbol.endswith("USD")
            tif = TimeInForce.GTC if is_crypto else TimeInForce.DAY
            request = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=tif,
            )
            order = self.client.submit_order(request)
            logger.info(f"Market order submitted: {symbol} {side} {qty}")
            return OrderResult(
                success=True,
                order_id=str(order.id),
                filled_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                filled_qty=float(order.filled_qty) if order.filled_qty else None,
                status=str(order.status),
                message="Order submitted",
            )
        except Exception as e:
            logger.error(f"Market order failed: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                filled_price=None,
                filled_qty=None,
                status="failed",
                message=str(e),
            )

    def submit_limit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        limit_price: float,
    ) -> OrderResult:
        """Submit limit order."""
        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            request = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.IOC,
                limit_price=limit_price,
            )
            order = self.client.submit_order(request)
            logger.info(f"Limit order submitted: {symbol} {side} {qty} @ {limit_price} (IOC)")
            return OrderResult(
                success=True,
                order_id=str(order.id),
                filled_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                filled_qty=float(order.filled_qty) if order.filled_qty else None,
                status=str(order.status),
                message="Order submitted",
            )
        except Exception as e:
            logger.error(f"Limit order failed: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                filled_price=None,
                filled_qty=None,
                status="failed",
                message=str(e),
            )

    def submit_bracket_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        stop_loss: float,
        take_profit: float,
        limit_price: float = None,
    ) -> OrderResult:
        """Submit bracket order with stop loss and take profit."""
        try:
            from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
            from alpaca.trading.enums import OrderClass

            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            if limit_price:
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price,
                    order_class=OrderClass.BRACKET,
                    stop_loss=StopLossRequest(stop_price=stop_loss),
                    take_profit=TakeProfitRequest(limit_price=take_profit),
                )
            else:
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=TimeInForce.GTC,
                    order_class=OrderClass.BRACKET,
                    stop_loss=StopLossRequest(stop_price=stop_loss),
                    take_profit=TakeProfitRequest(limit_price=take_profit),
                )

            order = self.client.submit_order(request)
            logger.info(f"Bracket order submitted: {symbol} {side} {qty} SL={stop_loss} TP={take_profit}")
            return OrderResult(
                success=True,
                order_id=str(order.id),
                filled_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                filled_qty=float(order.filled_qty) if order.filled_qty else None,
                status=str(order.status),
                message="Bracket order submitted",
            )
        except Exception as e:
            logger.error(f"Bracket order failed: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                filled_price=None,
                filled_qty=None,
                status="failed",
                message=str(e),
            )

    @staticmethod
    def _round_price(price: float) -> float:
        """Round price to valid penny increment for Alpaca."""
        return round(price, 2)

    def _wait_for_cancels(self, symbol: str, timeout: float = 5.0) -> bool:
        """Poll until no open orders remain for symbol."""
        import time
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            orders = self.get_open_orders()
            if not any(o["symbol"] == symbol for o in orders):
                return True
            time.sleep(0.3)
        logger.warning(f"Timed out waiting for {symbol} order cancellations")
        return False

    def replace_bracket_orders(
        self,
        symbol: str,
        qty: float,
        side: str,
        new_stop: float,
        new_tp: float,
    ) -> bool:
        """Cancel existing SL/TP orders and submit new OCO pair."""
        try:
            new_stop = self._round_price(new_stop)
            new_tp = self._round_price(new_tp)

            cancelled = self.cancel_orders_for_symbol(symbol)
            if cancelled > 0:
                self._wait_for_cancels(symbol)

            # Submit OCO order: stop loss + take profit share the position
            sell_side = "sell" if side.lower() == "buy" else "buy"
            from alpaca.trading.enums import OrderSide as OS, TimeInForce as TIF, OrderClass

            order_side = OS.SELL if sell_side == "sell" else OS.BUY

            oco_req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TIF.GTC,
                order_class=OrderClass.OCO,
                limit_price=new_tp,
                take_profit=TakeProfitRequest(limit_price=new_tp),
                stop_loss=StopLossRequest(stop_price=new_stop),
            )
            self.client.submit_order(oco_req)

            logger.info(f"Replaced bracket orders for {symbol}: SL={new_stop} TP={new_tp}")
            return True
        except Exception as e:
            logger.error(f"Failed to replace bracket orders for {symbol}: {e}")
            return False

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self.client.cancel_order_by_id(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False

    def cancel_orders_for_symbol(self, symbol: str) -> int:
        """Cancel all open orders for a symbol. Returns count cancelled."""
        cancelled = 0
        try:
            orders = self.get_open_orders()
            for order in orders:
                if order["symbol"] == symbol:
                    if self.cancel_order(order["id"]):
                        cancelled += 1
            if cancelled:
                logger.info(f"Cancelled {cancelled} orders for {symbol}")
        except Exception as e:
            logger.error(f"Failed to cancel orders for {symbol}: {e}")
        return cancelled

    def close_position(self, symbol: str) -> OrderResult:
        """Close entire position for symbol (cancels bracket orders first)."""
        try:
            # First cancel any open orders holding the shares
            self.cancel_orders_for_symbol(symbol)

            # Small delay to let cancellations process
            import time
            time.sleep(0.5)

            order = self.client.close_position(symbol)
            logger.info(f"Position closed: {symbol}")
            return OrderResult(
                success=True,
                order_id=str(order.id) if hasattr(order, 'id') else None,
                filled_price=None,
                filled_qty=None,
                status="closing",
                message="Position close submitted",
            )
        except Exception as e:
            logger.error(f"Close position failed: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                filled_price=None,
                filled_qty=None,
                status="failed",
                message=str(e),
            )

    def get_open_orders(self) -> List[dict]:
        """Get all open orders."""
        @_retry(max_retries=3, base_delay=1.0)
        def _get_open_orders_inner():
            request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            orders = self.client.get_orders(request)
            return [
                {
                    "id": str(o.id),
                    "symbol": o.symbol,
                    "side": o.side.value if hasattr(o.side, 'value') else str(o.side),
                    "qty": float(o.qty),
                    "filled_qty": float(o.filled_qty) if o.filled_qty else 0,
                    "type": o.type.value if hasattr(o.type, 'value') else str(o.type),
                    "status": o.status.value if hasattr(o.status, 'value') else str(o.status),
                    "limit_price": float(o.limit_price) if o.limit_price else None,
                    "stop_price": float(o.stop_price) if o.stop_price else None,
                }
                for o in orders
            ]

        try:
            return _get_open_orders_inner()
        except Exception as e:
            logger.error(f"Get orders failed: {e}")
            return []
