"""Options position tracking and exit management."""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config import settings
from src.trading.options.contracts import OptionContract
from src.trading.options.executor import OptionsExecutor

logger = logging.getLogger(__name__)


def _get_positions_file() -> Path:
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    prefix = "live" if mode == "live" else "paper"
    return Path(__file__).parent.parent.parent.parent / "logs" / f"{prefix}_options_positions.json"


@dataclass
class OptionsPosition:
    strategy: str          # "directional", "covered_call", "credit_spread"
    underlying: str
    contracts: list        # list of contract symbol strings
    entry_time: str
    net_debit_credit: float  # positive=debit, negative=credit
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
        self.positions: dict[str, OptionsPosition] = {}  # key = primary contract symbol
        self._file = _get_positions_file()
        self._load()

    def _load(self):
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                for key, val in data.get("positions", {}).items():
                    self.positions[key] = OptionsPosition(**val)
            except Exception:
                pass

    def _save(self):
        try:
            self._file.parent.mkdir(exist_ok=True)
            data = {
                "positions": {k: asdict(v) for k, v in self.positions.items()},
                "updated": datetime.now().isoformat(),
            }
            self._file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save options positions: {e}")

    def can_open(self) -> bool:
        open_count = sum(1 for p in self.positions.values() if p.status == "open")
        return open_count < settings.OPTIONS_MAX_CONCURRENT

    def open_directional(
        self, contract: OptionContract, qty: int, score: float, underlying_price: float
    ) -> bool:
        """Open a directional options position."""
        if not self.can_open():
            logger.warning("Max options positions reached")
            return False

        limit_price = contract.mid or contract.ask or 0
        if limit_price <= 0:
            logger.warning(f"No price for {contract.symbol} (bid={contract.bid}, ask={contract.ask})")
            return False

        result = self.executor.buy_option(contract.symbol, qty, limit_price)
        if not result.success:
            logger.warning(f"BTO failed for {contract.symbol}: {result.message}")
            return False

        cost = limit_price * qty * 100
        self.positions[contract.symbol] = OptionsPosition(
            strategy="directional",
            underlying=contract.underlying,
            contracts=[contract.symbol],
            entry_time=datetime.now().isoformat(),
            net_debit_credit=cost,
            max_loss=cost,
            max_profit=cost * 3,  # theoretical
            score=score,
            profit_target_pct=settings.OPTIONS_PROFIT_TARGET_DIRECTIONAL,
            stop_loss_pct=settings.OPTIONS_STOP_LOSS_DIRECTIONAL,
            dte_exit=settings.OPTIONS_DTE_EXIT,
            entry_underlying_price=underlying_price,
        )
        self._save()
        logger.info(f"Opened directional: {contract.symbol}, {qty}x @ ${limit_price:.2f}")
        return True

    def open_covered_call(
        self, contract: OptionContract, qty: int, underlying_price: float
    ) -> bool:
        """Open a covered call position."""
        if not self.can_open():
            return False

        limit_price = contract.mid or contract.bid or 0
        if limit_price <= 0:
            return False

        result = self.executor.sell_option(contract.symbol, qty, limit_price)
        if not result.success:
            return False

        premium = limit_price * qty * 100
        self.positions[contract.symbol] = OptionsPosition(
            strategy="covered_call",
            underlying=contract.underlying,
            contracts=[contract.symbol],
            entry_time=datetime.now().isoformat(),
            net_debit_credit=-premium,  # credit received
            max_loss=0,  # covered by shares
            max_profit=premium,
            score=0,
            profit_target_pct=0.80,  # let most decay
            stop_loss_pct=0,
            dte_exit=settings.OPTIONS_DTE_EXIT,
            entry_underlying_price=underlying_price,
        )
        self._save()
        logger.info(f"Opened covered call: {contract.symbol}, {qty}x @ ${limit_price:.2f}")
        return True

    def open_credit_spread(
        self,
        short_contract: OptionContract,
        long_contract: OptionContract,
        qty: int,
        score: float,
    ) -> bool:
        """Open a credit spread."""
        if not self.can_open():
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
        self.positions[key] = OptionsPosition(
            strategy="credit_spread",
            underlying=short_contract.underlying,
            contracts=[short_contract.symbol, long_contract.symbol],
            entry_time=datetime.now().isoformat(),
            net_debit_credit=-net_credit,
            max_loss=max_loss,
            max_profit=net_credit,
            score=score,
            profit_target_pct=settings.OPTIONS_PROFIT_TARGET_SPREAD,
            stop_loss_pct=2.0,  # close if loss > 2x credit
            dte_exit=settings.OPTIONS_DTE_EXIT,
            entry_underlying_price=short_contract.strike,
        )
        self._save()
        logger.info(
            f"Opened spread: {short_contract.symbol}/{long_contract.symbol}, "
            f"{qty}x, credit=${credit:.2f}"
        )
        return True

    def check_exits(self, get_option_price_fn) -> List[str]:
        """Check all option positions for exit triggers. Returns closed keys."""
        closed = []
        now = datetime.now()

        for key, pos in list(self.positions.items()):
            if pos.status != "open":
                continue

            should_close = False
            reason = ""

            # Check DTE
            entry_dt = datetime.fromisoformat(pos.entry_time)
            # Rough DTE check: if held > 5 days for directional
            held_days = (now - entry_dt).days

            if pos.strategy == "directional":
                # Get current option price
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
                # Check if we've captured enough profit
                # Would need current spread price; approximate via held time
                if held_days >= 20:
                    should_close = True
                    reason = "dte_expiry_approaching"

            elif pos.strategy == "covered_call":
                # Check if underlying dropped below entry
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
        """Close an options position. Returns True if closed or already gone."""
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
            self._save()
        else:
            logger.warning(f"Close failed for {key}, keeping status=open for retry")

        return all_ok

    def has_covered_call(self, underlying: str) -> bool:
        """Check if we already have a covered call on this underlying."""
        return any(
            p.strategy == "covered_call" and p.underlying == underlying and p.status == "open"
            for p in self.positions.values()
        )

    def get_options_summary(self) -> List[dict]:
        """Get summary of open options positions."""
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
