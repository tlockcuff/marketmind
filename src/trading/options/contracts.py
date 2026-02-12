"""Options contract selection."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from src.utils import utcnow
from typing import Optional, Tuple

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest
from alpaca.trading.enums import AssetStatus, ContractType

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class OptionContract:
    symbol: str           # OCC symbol e.g. AAPL240119C00190000
    underlying: str
    expiration: str       # YYYY-MM-DD
    strike: float
    option_type: str      # "call" or "put"
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    iv: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    open_interest: int = 0
    volume: int = 0
    dte: int = 0

    @property
    def spread_pct(self) -> float:
        if self.bid and self.ask and self.mid and self.mid > 0:
            return (self.ask - self.bid) / self.mid
        return 1.0


class ContractSelector:
    def __init__(self, trading_client: TradingClient):
        self.client = trading_client

    def find_directional_contract(
        self, underlying: str, direction: str, price: float, score: float
    ) -> Optional[OptionContract]:
        """Find best contract for directional play (buy call/put)."""
        option_type = "call" if direction in ("buy", "long") else "put"

        # Delta range — aggressive, wider for more leverage
        if score >= 80:
            delta_min, delta_max = 0.55, 0.70
        else:
            delta_min, delta_max = 0.40, 0.60

        contracts = self._get_chain(
            underlying, option_type,
            dte_min=settings.get("options_dte_min"),
            dte_max=settings.get("options_dte_max"),
        )
        if not contracts:
            return None

        # Filter: OI, spread (skip if unknown), delta (skip if unknown)
        candidates = []
        for c in contracts:
            if c.open_interest < settings.get("options_min_open_interest"):
                continue
            # Only filter spread if we have quote data
            if c.bid is not None and c.ask is not None:
                if c.spread_pct > settings.get("options_max_spread_pct"):
                    continue
            if c.delta is not None:
                abs_delta = abs(c.delta)
                if abs_delta < delta_min or abs_delta > delta_max:
                    continue
            candidates.append(c)

        # If greeks-based filtering left nothing, fallback to strike proximity
        if not candidates:
            candidates = self._fallback_by_strike(contracts, price, option_type)

        if not candidates:
            logger.info(f"No liquid {option_type} contracts for {underlying}")
            return None

        # Prefer contracts with known delta; among those, pick highest OI
        with_delta = [c for c in candidates if c.delta is not None]
        pool = with_delta if with_delta else candidates
        best = max(pool, key=lambda c: c.open_interest)
        logger.info(
            f"Selected {best.symbol}: delta={best.delta}, DTE={best.dte}, "
            f"OI={best.open_interest}, mid=${best.mid}"
        )
        return best

    def _fallback_by_strike(
        self, contracts: list, price: float, option_type: str
    ) -> list:
        """When greeks unavailable, pick near-ATM contracts by strike proximity."""
        # For calls: strike slightly above price (ATM to 5% OTM)
        # For puts: strike slightly below price (ATM to 5% OTM)
        candidates = []
        for c in contracts:
            if c.open_interest < settings.get("options_min_open_interest"):
                continue
            moneyness = (c.strike - price) / price
            if option_type == "call":
                # ATM to slightly OTM: -2% to +5%
                if -0.02 <= moneyness <= 0.05:
                    candidates.append(c)
            else:
                # ATM to slightly OTM: -5% to +2%
                if -0.05 <= moneyness <= 0.02:
                    candidates.append(c)
        return candidates

    def find_covered_call_contract(
        self, underlying: str, price: float, shares: int
    ) -> Optional[OptionContract]:
        """Find covered call contract: OTM call, delta 0.20-0.30."""
        if shares < 100:
            return None

        contracts = self._get_chain(
            underlying, "call",
            dte_min=14,
            dte_max=settings.get("options_dte_max_spread"),
        )
        if not contracts:
            return None

        delta_min, delta_max = settings.get("options_cc_delta_range")
        otm_min = price * 1.03
        otm_max = price * 1.08

        candidates = []
        for c in contracts:
            if c.strike < otm_min or c.strike > otm_max:
                continue
            if c.open_interest < settings.get("options_min_open_interest"):
                continue
            if c.bid is not None and c.ask is not None:
                if c.spread_pct > settings.get("options_max_spread_pct"):
                    continue
            if c.delta is not None:
                abs_delta = abs(c.delta)
                if abs_delta < delta_min or abs_delta > delta_max:
                    continue
            # Check minimum premium only if we have quote data
            if c.mid and c.mid / price < settings.get("covered_call_min_premium_pct"):
                continue
            candidates.append(c)

        if not candidates:
            logger.info(f"No suitable covered call contracts for {underlying}")
            return None

        # Pick best premium among valid candidates
        best = max(candidates, key=lambda c: c.mid or 0)
        logger.info(
            f"CC selected {best.symbol}: strike=${best.strike}, "
            f"mid=${best.mid}, DTE={best.dte}"
        )
        return best

    def find_spread_contracts(
        self, underlying: str, direction: str, price: float
    ) -> Optional[Tuple[OptionContract, OptionContract]]:
        """Find credit spread pair (short + long legs).

        Bull put spread for buy signals, bear call spread for sell signals.
        """
        if direction in ("buy", "long"):
            option_type = "put"
        else:
            option_type = "call"

        contracts = self._get_chain(
            underlying, option_type,
            dte_min=14,
            dte_max=settings.get("options_dte_max_spread"),
        )
        if not contracts:
            return None

        # Find short leg: delta 0.25-0.35, or by strike if no greeks
        short_candidates = []
        for c in contracts:
            if c.open_interest < settings.get("options_min_open_interest"):
                continue
            if c.bid is not None and c.ask is not None:
                if c.spread_pct > settings.get("options_max_spread_pct"):
                    continue
            if c.delta is not None:
                abs_delta = abs(c.delta)
                if 0.25 <= abs_delta <= 0.35:
                    short_candidates.append(c)
            else:
                # No greeks: use ~5-10% OTM as proxy for 0.25-0.35 delta
                moneyness = abs(c.strike - price) / price
                if 0.05 <= moneyness <= 0.10:
                    short_candidates.append(c)

        if not short_candidates:
            return None

        short_leg = max(short_candidates, key=lambda c: c.open_interest)

        # Find long leg: same expiry, $2-5 further OTM
        long_candidates = []
        for c in contracts:
            if c.expiration != short_leg.expiration:
                continue
            if c.open_interest < 50:
                continue
            width = abs(c.strike - short_leg.strike)
            if width < 2.0 or width > 5.0:
                continue
            # Long leg further OTM
            if option_type == "put" and c.strike >= short_leg.strike:
                continue
            if option_type == "call" and c.strike <= short_leg.strike:
                continue
            long_candidates.append(c)

        if not long_candidates:
            return None

        # Pick long leg closest to $2-5 width
        long_leg = min(long_candidates, key=lambda c: abs(abs(c.strike - short_leg.strike) - 3.0))

        # Check min credit: 30% of width
        width = abs(short_leg.strike - long_leg.strike)
        short_mid = short_leg.mid or 0
        long_mid = long_leg.mid or 0
        credit = short_mid - long_mid
        if credit <= 0 or credit / width < 0.30:
            logger.info(f"Spread credit too thin: ${credit:.2f} on ${width:.0f} width")
            return None

        logger.info(
            f"Spread: short {short_leg.symbol} / long {long_leg.symbol}, "
            f"credit=${credit:.2f}, width=${width:.0f}"
        )
        return (short_leg, long_leg)

    def _get_chain(
        self, underlying: str, option_type: str, dte_min: int, dte_max: int
    ) -> list[OptionContract]:
        """Fetch option chain from Alpaca and return parsed contracts."""
        try:
            now = utcnow()
            # 0DTE: use today's date as minimum
            exp_min = (now + timedelta(days=max(0, dte_min))).strftime("%Y-%m-%d")
            exp_max = (now + timedelta(days=dte_max)).strftime("%Y-%m-%d")

            contract_type = ContractType.CALL if option_type == "call" else ContractType.PUT

            request = GetOptionContractsRequest(
                underlying_symbols=[underlying],
                status=AssetStatus.ACTIVE,
                expiration_date_gte=exp_min,
                expiration_date_lte=exp_max,
                type=contract_type,
            )
            response = self.client.get_option_contracts(request)
            contracts_data = response.option_contracts or []

            results = []
            for c in contracts_data:
                exp_date = str(c.expiration_date) if c.expiration_date else ""
                dte = (datetime.strptime(exp_date, "%Y-%m-%d") - now).days if exp_date else 0

                contract = OptionContract(
                    symbol=c.symbol,
                    underlying=underlying,
                    expiration=exp_date,
                    strike=float(c.strike_price),
                    option_type=option_type,
                    open_interest=int(c.open_interest) if c.open_interest else 0,
                    dte=dte,
                )
                results.append(contract)

            # Batch fetch snapshots for greeks/quotes
            if results:
                self._populate_greeks(results)

            greeks_count = sum(1 for c in results if c.delta is not None)
            logger.info(
                f"Got {len(results)} {option_type} contracts for {underlying} "
                f"({greeks_count} with greeks)"
            )
            return results

        except Exception as e:
            logger.error(f"Failed to get option chain for {underlying}: {e}")
            return []

    def _populate_greeks(self, contracts: list[OptionContract]):
        """Populate greeks and quotes via Alpaca option snapshots."""
        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionSnapshotRequest
        except ImportError:
            logger.warning("Alpaca options data SDK not available, greeks will be empty")
            return

        try:
            data_client = OptionHistoricalDataClient(
                api_key=settings.ALPACA_API_KEY,
                secret_key=settings.ALPACA_SECRET_KEY,
            )

            # Process in batches of 50
            for i in range(0, len(contracts), 50):
                batch = contracts[i:i + 50]
                symbols = [c.symbol for c in batch]

                try:
                    request = OptionSnapshotRequest(symbol_or_symbols=symbols)
                    snapshots = data_client.get_option_snapshot(request)
                except Exception as e:
                    logger.warning(f"Snapshot batch {i} failed: {e}")
                    continue

                for contract in batch:
                    snap = snapshots.get(contract.symbol)
                    if not snap:
                        continue
                    if hasattr(snap, "greeks") and snap.greeks:
                        contract.delta = getattr(snap.greeks, "delta", None)
                        contract.gamma = getattr(snap.greeks, "gamma", None)
                        contract.theta = getattr(snap.greeks, "theta", None)
                        contract.iv = getattr(snap.greeks, "mid_iv", None)
                    if hasattr(snap, "latest_quote") and snap.latest_quote:
                        q = snap.latest_quote
                        contract.bid = float(q.bid_price) if getattr(q, "bid_price", None) else None
                        contract.ask = float(q.ask_price) if getattr(q, "ask_price", None) else None
                        if contract.bid and contract.ask:
                            contract.mid = (contract.bid + contract.ask) / 2
                    if hasattr(snap, "latest_trade") and snap.latest_trade:
                        t = snap.latest_trade
                        contract.volume = int(t.size) if getattr(t, "size", None) else 0

        except Exception as e:
            logger.warning(f"Failed to populate greeks: {e}")
