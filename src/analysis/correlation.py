"""Position correlation filter.

Prevents opening positions too correlated with existing holdings.
Uses sector + simple price correlation from recent daily returns.
"""
import logging
import numpy as np
from typing import Optional
from src.analysis.market_data import MarketDataFetcher

logger = logging.getLogger(__name__)

# Tickers known to be highly correlated
CORRELATED_PAIRS = {
    frozenset({"XOM", "CVX"}),
    frozenset({"SLB", "HAL"}),
    frozenset({"LMT", "NOC", "RTX", "GD", "BA"}),
    frozenset({"AAPL", "MSFT"}),
    frozenset({"GOOGL", "GOOG"}),
    frozenset({"META", "SNAP"}),
    frozenset({"JPM", "BAC", "GS", "MS"}),
    frozenset({"AMD", "NVDA", "INTC"}),
}

def check_correlation(new_symbol: str, existing_symbols: set, market_data: MarketDataFetcher = None) -> tuple[bool, str]:
    """Check if new_symbol is too correlated with existing positions.
    
    Returns (ok_to_trade, reason).
    """
    if not existing_symbols:
        return True, "no existing positions"
    
    # Quick check: known correlated pairs
    for pair in CORRELATED_PAIRS:
        if new_symbol in pair:
            overlap = pair & existing_symbols
            if len(overlap) >= 2:
                return False, f"{new_symbol} too correlated with {overlap} (max 2 per correlated group)"
    
    # Price correlation check (if market_data available)
    if market_data and len(existing_symbols) >= 3:
        try:
            high_corr = _check_price_correlation(new_symbol, existing_symbols, market_data)
            if high_corr:
                return False, f"{new_symbol} price-correlated >0.80 with {high_corr}"
        except Exception as e:
            logger.debug(f"Correlation check failed: {e}")
    
    return True, "ok"

def _check_price_correlation(new_symbol: str, existing: set, market_data: MarketDataFetcher) -> Optional[str]:
    """Check 20-day return correlation between new symbol and existing positions."""
    try:
        new_bars = market_data.get_bars(new_symbol, days=25)
        if new_bars is None or len(new_bars) < 20:
            return None
        new_returns = new_bars['close'].pct_change().dropna().tail(20)
        
        for sym in list(existing)[:5]:  # Check top 5 to limit API calls
            bars = market_data.get_bars(sym, days=25)
            if bars is None or len(bars) < 20:
                continue
            returns = bars['close'].pct_change().dropna().tail(20)
            if len(returns) != len(new_returns):
                continue
            corr = np.corrcoef(new_returns.values, returns.values)[0, 1]
            if abs(corr) > 0.80:
                return sym
    except Exception:
        pass
    return None
