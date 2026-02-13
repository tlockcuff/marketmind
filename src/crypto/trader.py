"""CryptoTrader — manages crypto positions with local stop/target management."""

import json
import logging
from typing import Optional

from config import settings
from src.utils import utcnow, ensure_aware
from src.db import get_db
from src.trading.alpaca_client import AlpacaClient
from src.trading.trade_history import get_trade_history
from src.signals.grok_client import GrokClient
from src.notifications.discord import DiscordNotifier
from src.crypto.scanner import CryptoScanner
from src.crypto.config import (
    CRYPTO_MAX_POSITION_PCT,
    CRYPTO_MAX_CONCURRENT,
    CRYPTO_STOP_LOSS_PCT,
    CRYPTO_TAKE_PROFIT_PCT,
    CRYPTO_TRAILING_STOP_PCT,
    CRYPTO_MIN_SCORE_THRESHOLD,
    CRYPTO_SCALE_OUT_1_PCT,
    CRYPTO_SCALE_OUT_2_PCT,
)

logger = logging.getLogger(__name__)


def _mode() -> str:
    import os
    return "live" if os.environ.get("TRADING_MODE", "paper").lower() == "live" else "paper"


class CryptoPosition:
    """In-memory representation of an open crypto position."""
    __slots__ = (
        "symbol", "qty", "original_qty", "entry_price", "entry_time",
        "stop_loss", "take_profit", "trailing_stop", "score",
        "direction", "scale_out_level", "atr",
    )

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class CryptoTrader:
    """Autonomous crypto trader — 24/7, no PDT rules, local stop management."""

    def __init__(self, alpaca: AlpacaClient, grok: GrokClient, discord: DiscordNotifier):
        self.alpaca = alpaca
        self.grok = grok
        self.discord = discord
        self.scanner = CryptoScanner(grok)
        self.positions: dict[str, CryptoPosition] = {}  # symbol -> CryptoPosition
        self._sync_positions()

    # ------------------------------------------------------------------
    # Position sync
    # ------------------------------------------------------------------

    def _sync_positions(self):
        """Load open crypto positions from DB into memory."""
        mode = _mode()
        try:
            with get_db() as conn:
                rows = conn.execute(
                    """SELECT symbol, direction, qty, entry_price, entry_time,
                              stop_loss, take_profit, score, atr_at_entry,
                              scale_out_level
                       FROM trades
                       WHERE mode = %s AND status = 'open' AND asset_type = 'crypto'""",
                    (mode,),
                ).fetchall()
                for r in rows:
                    symbol = r[0]
                    entry_price = float(r[3]) if r[3] else 0
                    atr = float(r[8]) if r[8] else entry_price * CRYPTO_TRAILING_STOP_PCT
                    self.positions[symbol] = CryptoPosition(
                        symbol=symbol,
                        direction=r[1],
                        qty=float(r[2]),
                        original_qty=float(r[2]),
                        entry_price=entry_price,
                        entry_time=r[4],
                        stop_loss=float(r[5]) if r[5] else entry_price * (1 - CRYPTO_STOP_LOSS_PCT),
                        take_profit=float(r[6]) if r[6] else entry_price * (1 + CRYPTO_TAKE_PROFIT_PCT),
                        trailing_stop=float(r[5]) if r[5] else entry_price * (1 - CRYPTO_TRAILING_STOP_PCT),
                        score=float(r[7]) if r[7] else 0,
                        scale_out_level=r[9] or 0,
                        atr=atr,
                    )
            logger.info(f"Crypto: synced {len(self.positions)} open positions")
        except Exception as e:
            logger.warning(f"Crypto position sync failed: {e}")

    # ------------------------------------------------------------------
    # Capacity check
    # ------------------------------------------------------------------

    def can_open(self) -> bool:
        return len(self.positions) < CRYPTO_MAX_CONCURRENT

    # ------------------------------------------------------------------
    # Trading cycle
    # ------------------------------------------------------------------

    def run_cycle(self):
        """One full crypto trading cycle: check exits then scan for entries."""
        logger.info("=== Crypto trading cycle ===")
        self._check_positions()
        if self.can_open():
            self._scan_and_enter()
        else:
            logger.info(f"Crypto: {len(self.positions)}/{CRYPTO_MAX_CONCURRENT} positions, skipping scan")
        logger.info("=== Crypto cycle complete ===")

    # ------------------------------------------------------------------
    # Exit management (local stops — no bracket orders for crypto)
    # ------------------------------------------------------------------

    def _check_positions(self):
        """Check all open crypto positions for stop/target/scale-out."""
        to_close = []
        for symbol, pos in list(self.positions.items()):
            price = self.scanner.get_crypto_price(symbol)
            if price is None:
                logger.warning(f"Crypto: no price for {symbol}, skipping check")
                continue

            is_long = pos.direction in ("buy", "long")
            pl_pct = (price - pos.entry_price) / pos.entry_price if is_long else (pos.entry_price - price) / pos.entry_price

            # --- Trailing stop update ---
            if is_long:
                new_trail = price * (1 - CRYPTO_TRAILING_STOP_PCT)
                if pos.atr:
                    new_trail = max(new_trail, price - 2 * pos.atr)
                if new_trail > pos.trailing_stop:
                    pos.trailing_stop = new_trail
                    pos.stop_loss = max(pos.stop_loss, new_trail)
            else:
                new_trail = price * (1 + CRYPTO_TRAILING_STOP_PCT)
                if pos.atr:
                    new_trail = min(new_trail, price + 2 * pos.atr)
                if new_trail < pos.trailing_stop:
                    pos.trailing_stop = new_trail
                    pos.stop_loss = min(pos.stop_loss, new_trail)

            # --- Stop loss hit ---
            if (is_long and price <= pos.stop_loss) or (not is_long and price >= pos.stop_loss):
                logger.info(f"Crypto STOP HIT: {symbol} @ ${price:.2f} (stop={pos.stop_loss:.2f})")
                self._close_position(symbol, price, "stop_loss")
                to_close.append(symbol)
                continue

            # --- Take profit hit ---
            if (is_long and price >= pos.take_profit) or (not is_long and price <= pos.take_profit):
                logger.info(f"Crypto TARGET HIT: {symbol} @ ${price:.2f} (tp={pos.take_profit:.2f})")
                self._close_position(symbol, price, "take_profit")
                to_close.append(symbol)
                continue

            # --- Scale-out logic ---
            if pos.scale_out_level == 0 and pl_pct >= CRYPTO_SCALE_OUT_1_PCT:
                trim_qty = max(1, int(pos.original_qty * 0.33))
                if trim_qty < pos.qty:
                    self._partial_close(symbol, trim_qty, price, "scale_out_1")
                    pos.scale_out_level = 1

            elif pos.scale_out_level == 1 and pl_pct >= CRYPTO_SCALE_OUT_2_PCT:
                trim_qty = max(1, int(pos.original_qty * 0.33))
                if trim_qty < pos.qty:
                    self._partial_close(symbol, trim_qty, price, "scale_out_2")
                    pos.scale_out_level = 2

        for s in to_close:
            self.positions.pop(s, None)

    # ------------------------------------------------------------------
    # Order execution helpers
    # ------------------------------------------------------------------

    def _close_position(self, symbol: str, price: float, reason: str):
        """Close entire crypto position."""
        pos = self.positions.get(symbol)
        if not pos:
            return
        side = "sell" if pos.direction in ("buy", "long") else "buy"
        result = self.alpaca.submit_market_order(symbol=symbol, qty=pos.qty, side=side)
        if result.success:
            get_trade_history().record_close(symbol, price, reason)
            self.discord.alert("Crypto Exit", f"{symbol} closed @ ${price:,.2f} ({reason})", "warning")
            logger.info(f"Crypto closed {symbol}: {reason} @ ${price:,.2f}")
        else:
            logger.error(f"Crypto close failed for {symbol}: {result.message}")

    def _partial_close(self, symbol: str, qty: float, price: float, reason: str):
        """Sell part of a crypto position."""
        pos = self.positions.get(symbol)
        if not pos:
            return
        side = "sell" if pos.direction in ("buy", "long") else "buy"
        result = self.alpaca.submit_market_order(symbol=symbol, qty=qty, side=side)
        if result.success:
            pos.qty -= qty
            # Update DB qty
            mode = _mode()
            try:
                with get_db() as conn:
                    conn.execute(
                        "UPDATE trades SET qty = %s, scale_out_level = %s WHERE mode = %s AND symbol = %s AND status = 'open' AND asset_type = 'crypto'",
                        (pos.qty, pos.scale_out_level, mode, symbol),
                    )
                    conn.commit()
            except Exception as e:
                logger.warning(f"Crypto partial close DB update failed: {e}")
            self.discord.alert("Crypto Scale-Out", f"{symbol} -{qty} @ ${price:,.2f} ({reason})", "info")
            logger.info(f"Crypto scale-out {symbol}: -{qty} @ ${price:,.2f} ({reason})")
        else:
            logger.error(f"Crypto partial close failed for {symbol}: {result.message}")

    # ------------------------------------------------------------------
    # Scan + entry
    # ------------------------------------------------------------------

    def _scan_and_enter(self):
        """Scan for crypto signals and open positions."""
        signals = self.scanner.scan()
        logger.info(f"Crypto: evaluating {len(signals)} signals")

        for signal in signals:
            if not self.can_open():
                break

            # Skip if already in position
            if signal.ticker in self.positions:
                continue

            if signal.confidence < CRYPTO_MIN_SCORE_THRESHOLD:
                continue

            self._execute_entry(signal)

    def _execute_entry(self, signal):
        """Open a new crypto position."""
        symbol = signal.ticker
        price = self.scanner.get_crypto_price(symbol)
        if price is None:
            logger.warning(f"Crypto: no price for {symbol}, skipping entry")
            return

        # Position sizing
        account = self.alpaca.get_account()
        if not account:
            return
        equity = account.get("equity", 0)
        position_value = equity * CRYPTO_MAX_POSITION_PCT
        qty = position_value / price
        # Crypto allows fractional — round to reasonable precision
        if price > 1000:
            qty = round(qty, 4)
        elif price > 1:
            qty = round(qty, 2)
        else:
            qty = round(qty, 0)

        if qty <= 0:
            return

        # Compute stops
        atr = None
        df = self.scanner.get_crypto_bars(symbol, days=30, timeframe="1d")
        if df is not None and len(df) >= 14:
            from src.analysis.indicators import calculate_indicators
            ind = calculate_indicators(df)
            if ind:
                atr = ind.atr

        if signal.direction in ("buy", "long"):
            stop_loss = round(price * (1 - CRYPTO_STOP_LOSS_PCT), 2)
            take_profit = round(price * (1 + CRYPTO_TAKE_PROFIT_PCT), 2)
        else:
            stop_loss = round(price * (1 + CRYPTO_STOP_LOSS_PCT), 2)
            take_profit = round(price * (1 - CRYPTO_TAKE_PROFIT_PCT), 2)

        side = "buy" if signal.direction in ("buy", "long") else "sell"
        result = self.alpaca.submit_market_order(symbol=symbol, qty=qty, side=side)
        if not result.success:
            logger.warning(f"Crypto entry failed for {symbol}: {result.message}")
            return

        # Record in DB
        get_trade_history().record_open(
            symbol=symbol,
            direction=signal.direction,
            qty=qty,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            score=signal.confidence,
            grok_rationale=signal.rationale or "",
            score_breakdown={"signal_source": signal.signal_source},
            sector=None,
            atr_at_entry=atr,
            signal_source=signal.signal_source,
        )

        # Mark asset_type = 'crypto' in DB
        mode = _mode()
        try:
            with get_db() as conn:
                conn.execute(
                    "UPDATE trades SET asset_type = 'crypto' WHERE mode = %s AND symbol = %s AND status = 'open' AND asset_type = 'stock'",
                    (mode, symbol),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to set asset_type for {symbol}: {e}")

        # Track locally
        self.positions[symbol] = CryptoPosition(
            symbol=symbol,
            direction=signal.direction,
            qty=qty,
            original_qty=qty,
            entry_price=price,
            entry_time=utcnow(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=stop_loss,
            score=signal.confidence,
            scale_out_level=0,
            atr=atr,
        )

        self.discord.alert(
            "Crypto Entry",
            f"{side.upper()} {symbol} {qty} @ ${price:,.2f} (score={signal.confidence:.0f})\n{signal.rationale}",
            "info",
        )
        logger.info(f"Crypto opened {symbol}: {side} {qty} @ ${price:,.2f}")
