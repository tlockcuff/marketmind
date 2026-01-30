"""Options position sizing."""

import logging

from config import settings

logger = logging.getLogger(__name__)


class OptionsSizer:
    def __init__(self, equity: float):
        self.equity = equity

    def size_directional(self, score: float, contract_price: float) -> int:
        """Size directional option trade. Returns number of contracts (1-10)."""
        if contract_price <= 0:
            return 0

        max_loss = self.equity * settings.get("options_max_position_pct")
        # Each contract = 100 shares, cost = contract_price * 100
        cost_per_contract = contract_price * 100
        max_contracts = int(max_loss / cost_per_contract)

        # Scale by score
        if score >= 80:
            qty = max_contracts
        elif score >= 75:
            qty = int(max_contracts * 0.7)
        else:
            qty = int(max_contracts * 0.5)

        return max(1, min(10, qty))

    def size_covered_call(self, shares: int) -> int:
        """Size covered call: 1 contract per 100 shares."""
        return shares // 100

    def size_credit_spread(self, score: float, width: float, credit: float) -> int:
        """Size credit spread. Max risk = 3% equity."""
        if width <= 0 or credit <= 0:
            return 0

        max_risk_per_spread = (width - credit) * 100  # per contract
        if max_risk_per_spread <= 0:
            return 0

        total_max_risk = self.equity * 0.03
        max_contracts = int(total_max_risk / max_risk_per_spread)

        # Scale by score
        if score >= 85:
            qty = max_contracts
        else:
            qty = int(max_contracts * 0.6)

        return max(1, min(10, qty))
