"""Options position tracking and exit management — PostgreSQL backend."""

import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from src.utils import utcnow, ensure_aware
from typing import List, Optional

from config import settings
from src.db import get_db
from src.trading.options.contracts import OptionContract
from src.trading.options.executor import OptionsExecutor

logger = logging.getLogger(__name__)


def _mode() -> str:
    return "live" if os.environ.get("TRADING_MODE", "paper").lower() == "live" else "paper"


@dataclass
class OptionsPosition:
    strategy: str
    underlying: str
    contracts: list
    entry_time: str
    net_debit_credit: float
    max_loss: float
    max_profit: float
    score: float
    profit_target_pct: float
    stop_loss_pct: float
    dte_exit: int = 2
    entry_underlying_price: float = 0.0
    status: str = "open"


class OptionsPositionManager:
    def __init__(self, executor: OptionsExecutor):
        self.executor = executor
        self.positions: dict[str, OptionsPosition] = {}
        self._load()

    def _load(self):
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
                self.positions = {}
                for r in rows:
                    self.positions[r[0]] = OptionsPosition(
                        strategy=r[1],
                        underlying=r[2],
                        contracts=r[3] or [],
                        entry_time=r[4].isoformat() if r[4] else "",
                        net_debit_credit=float(r[5]) if r[5] else 0,
                        max_loss=float(r[6]) if r[6] else 0,
                        max_profit=float(r[7]) if r[7] else 0,
                        score=float(r[8]) if r[8] else 0,
                        profit_target_pct=float(r[9]) if r[9] else 0,
                        stop_loss_pct=float(r[10]) if r[10] else 0,
                        dte_exit=r[11] or 2,
                        entry_underlying_price=float(r[12]) if r[12] else 0,
                        status=r[13] or "open",
                    )
        except Exception as e:
            logger.warning(f"Failed to load options positions from DB: {e}")

    def _db_insert(self, key: str, pos: OptionsPosition):
        mode = _mode()
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO options_positions
                       (mode, key, strategy, underlying, contracts, entry_time,
                        net_debit_credit, max_loss, max_profit, score,
                        profit_target_pct, stop_loss_pct, dte_exit,
                        entry_underlying_price, status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open')""",
                    (mode, key, pos.strategy, pos.underlying,
                     json.dumps(pos.contracts), pos.entry_time,
                     pos.net_debit_credit, pos.max_loss, pos.max_profit,
                     pos.score, pos.profit_target_pct, pos.stop_loss_pct,
                     pos.dte_exit, pos.entry_underlying_price),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to save options position: {e}")

    def _db_update_status(self, key: str, status: str):
        mode = _mode()
        try:
            with get_db() as conn:
                conn.execute(
                    """UPDATE options_positions SET status = %s, updated_at = NOW()
                       WHERE mode = %s AND key = %s AND status = 'open'""",
                    (status, mode, key),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to update options position status: {e}")

    def can_open(self) -> bool:
        open_count = sum(1 for p in self.positions.values() if p.status == "open")
        return open_count < settings.get("options_max_concurrent")

    def open_directional(
        self, contract: OptionContract, qty: int, score: float, underlying_price: float
    ) -> bool:
        if not self.can_open():
            logger.warning("Max options positions reached")
            return False

        # Enforce minimum score for directional options (defense in depth)
        min_score = settings.get("options_min_score_directional")
        if score < min_score:
            logger.warning(
                f"Score {score:.0f} below options_min_score_directional ({min_score}) "
                f"for {contract.symbol} — blocking entry"
            )
            return False

        limit_price = contract.mid or contract.ask or 0
        if limit_price <= 0:
            logger.warning(f"No price for {contract.symbol}")
            return False

        result = self.executor.buy_option(contract.symbol, qty, limit_price)
        if not result.success:
            logger.warning(f"BTO failed for {contract.symbol}: {result.message}")
            return False

        cost = limit_price * qty * 100
        pos = OptionsPosition(
            strategy="directional",
            underlying=contract.underlying,
            contracts=[contract.symbol],
            entry_time=utcnow().isoformat(),
            net_debit_credit=cost,
            max_loss=cost,
            max_profit=cost * 3,
            score=score,
            profit_target_pct=settings.get("options_profit_target_directional"),
            stop_loss_pct=settings.get("options_stop_loss_directional"),
            dte_exit=settings.get("options_dte_exit"),
            entry_underlying_price=underlying_price,
        )
        self.positions[contract.symbol] = pos
        self._db_insert(contract.symbol, pos)
        logger.info(f"Opened directional: {contract.symbol}, {qty}x @ ${limit_price:.2f}")
        return True

    def open_covered_call(
        self, contract: OptionContract, qty: int, underlying_price: float
    ) -> bool:
        if not self.can_open():
            return False

        limit_price = contract.mid or contract.bid or 0
        if limit_price <= 0:
            return False

        result = self.executor.sell_option(contract.symbol, qty, limit_price)
        if not result.success:
            return False

        premium = limit_price * qty * 100
        pos = OptionsPosition(
            strategy="covered_call",
            underlying=contract.underlying,
            contracts=[contract.symbol],
            entry_time=utcnow().isoformat(),
            net_debit_credit=-premium,
            max_loss=0,
            max_profit=premium,
            score=0,
            profit_target_pct=0.80,
            stop_loss_pct=0,
            dte_exit=settings.get("options_dte_exit"),
            entry_underlying_price=underlying_price,
        )
        self.positions[contract.symbol] = pos
        self._db_insert(contract.symbol, pos)
        logger.info(f"Opened covered call: {contract.symbol}, {qty}x @ ${limit_price:.2f}")
        return True

    def open_credit_spread(
        self,
        short_contract: OptionContract,
        long_contract: OptionContract,
        qty: int,
        score: float,
    ) -> bool:
        if not self.can_open():
            return False

        # Enforce minimum score for spreads (defense in depth)
        min_score = settings.get("options_min_score_spread")
        if score < min_score:
            logger.warning(
                f"Score {score:.0f} below options_min_score_spread ({min_score}) "
                f"for {short_contract.symbol} — blocking entry"
            )
            return False

        short_price = short_contract.mid or short_contract.bid or 0
        long_price = long_contract.mid or long_contract.ask or 0
        credit = short_price - long_price
        if credit <= 0:
            return False

        result = self.executor.submit_credit_spread(
            short_contract.symbol, long_contract.symbol, qty, short_price
        )
        if not result.success:
            return False

        width = abs(short_contract.strike - long_contract.strike)
        net_credit = credit * qty * 100
        max_loss = (width - credit) * qty * 100

        key = short_contract.symbol
        pos = OptionsPosition(
            strategy="credit_spread",
            underlying=short_contract.underlying,
            contracts=[short_contract.symbol, long_contract.symbol],
            entry_time=utcnow().isoformat(),
            net_debit_credit=-net_credit,
            max_loss=max_loss,
            max_profit=net_credit,
            score=score,
            profit_target_pct=settings.get("options_profit_target_spread"),
            stop_loss_pct=2.0,
            dte_exit=settings.get("options_dte_exit"),
            entry_underlying_price=short_contract.strike,
        )
        self.positions[key] = pos
        self._db_insert(key, pos)
        logger.info(
            f"Opened spread: {short_contract.symbol}/{long_contract.symbol}, "
            f"{qty}x, credit=${credit:.2f}"
        )
        return True

    def check_exits(self, get_option_price_fn) -> List[str]:
        closed = []
        now = utcnow()

        for key, pos in list(self.positions.items()):
            if pos.status != "open":
                continue

            should_close = False
            reason = ""

            entry_dt = ensure_aware(datetime.fromisoformat(pos.entry_time))
            held_days = (now - entry_dt).days

            if pos.strategy == "directional":
                current_price = get_option_price_fn(pos.contracts[0])
                if current_price is not None:
                    entry_cost_per = pos.net_debit_credit / (100 * max(1, len(pos.contracts)))
                    pnl_pct = (current_price - entry_cost_per) / entry_cost_per if entry_cost_per > 0 else 0

                    if pnl_pct >= pos.profit_target_pct:
                        should_close = True
                        reason = f"profit_target ({pnl_pct:.0%})"
                    elif pnl_pct <= -pos.stop_loss_pct:
                        should_close = True
                        reason = f"stop_loss ({pnl_pct:.0%})"

                if held_days >= 5:
                    should_close = True
                    reason = f"max_hold_{held_days}d"

            elif pos.strategy == "credit_spread":
                if held_days >= 20:
                    should_close = True
                    reason = "dte_expiry_approaching"

            elif pos.strategy == "covered_call":
                current_underlying = get_option_price_fn(pos.underlying)
                if current_underlying and current_underlying < pos.entry_underlying_price * 0.97:
                    should_close = True
                    reason = "underlying_below_entry"

            if should_close:
                logger.info(f"Options exit: {key} — {reason}")
                if self._close_position(key, reason):
                    closed.append(key)

        return closed

    def _close_position(self, key: str, reason: str) -> bool:
        pos = self.positions.get(key)
        if not pos:
            return False

        all_ok = True
        if pos.strategy == "credit_spread" and len(pos.contracts) == 2:
            result = self.executor.close_spread(pos.contracts[0], pos.contracts[1], 1)
            all_ok = result.success
        else:
            for symbol in pos.contracts:
                result = self.executor.close_option_position(symbol)
                if not result.success:
                    all_ok = False
                    logger.error(f"Failed to close {symbol}: {result.message}")

        if all_ok:
            pos.status = f"closed_{reason}"
            self._db_update_status(key, pos.status)
        else:
            logger.warning(f"Close failed for {key}, keeping status=open for retry")

        return all_ok

    def has_covered_call(self, underlying: str) -> bool:
        return any(
            p.strategy == "covered_call" and p.underlying == underlying and p.status == "open"
            for p in self.positions.values()
        )

    def get_options_summary(self) -> List[dict]:
        results = []
        for key, pos in self.positions.items():
            if pos.status != "open":
                continue
            results.append({
                "key": key,
                "strategy": pos.strategy,
                "underlying": pos.underlying,
                "contracts": pos.contracts,
                "entry_time": pos.entry_time,
                "net_debit_credit": pos.net_debit_credit,
                "max_loss": pos.max_loss,
                "max_profit": pos.max_profit,
                "score": pos.score,
            })
        return results
