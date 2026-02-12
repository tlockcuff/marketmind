"""Earnings calendar filter.

Checks if stocks have upcoming earnings to reduce position size and avoid
earnings-related volatility.
"""

import logging
from datetime import datetime, timedelta, date
from src.utils import utcnow
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Module-level cache: {symbol: {"reports_soon": bool, "checked_at": datetime}}
_earnings_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


def has_upcoming_earnings(symbol: str) -> bool:
    """Check if stock has earnings today or tomorrow.

    Returns:
        True if earnings are imminent (today or tomorrow)
        False otherwise (or on check failure - fail-open design)
    """
    now = utcnow()

    # Check cache first
    if symbol in _earnings_cache:
        cache_entry = _earnings_cache[symbol]
        cached_at = cache_entry.get("checked_at")
        if cached_at and (now - cached_at).total_seconds() < _CACHE_TTL_SECONDS:
            result = cache_entry.get("reports_soon", False)
            logger.debug(f"{symbol}: using cached earnings check (reports_soon={result})")
            return result

    # Run the check
    reports_soon = _check_earnings_yfinance(symbol)

    # Cache the result
    _earnings_cache[symbol] = {
        "reports_soon": reports_soon,
        "checked_at": now,
    }

    if reports_soon:
        logger.warning(f"{symbol}: EARNINGS TODAY/TOMORROW - will reduce position size")

    return reports_soon


def _check_earnings_yfinance(symbol: str) -> bool:
    """Check yfinance for upcoming earnings.

    Returns:
        True if earnings are today or tomorrow
        False otherwise (or on any error - fail-open)
    """
    try:
        import yfinance as yf
        from dateutil import parser

        ticker = yf.Ticker(symbol)
        cal = ticker.calendar

        if cal is None or (hasattr(cal, 'empty') and cal.empty):
            return False

        # Handle both dict and DataFrame formats
        earnings_date = None

        if isinstance(cal, dict):
            # Dictionary format: look for 'Earnings Date' key
            earnings_raw = cal.get('Earnings Date')
            if earnings_raw is not None:
                # Handle list values (take first element)
                if isinstance(earnings_raw, list):
                    earnings_raw = earnings_raw[0] if earnings_raw else None
                earnings_date = earnings_raw
        else:
            # DataFrame format
            try:
                # Try accessing by column name
                earnings_date = cal['Earnings Date'].iloc[0]
            except (KeyError, IndexError, AttributeError):
                try:
                    # Fallback: try first cell
                    earnings_date = cal.iloc[0, 0]
                except (IndexError, AttributeError):
                    return False

        if earnings_date is None:
            return False

        # Parse the date (handle Timestamp, date, or string)
        if hasattr(earnings_date, 'date'):
            # Pandas Timestamp with .date() method
            earnings_date = earnings_date.date()
        elif isinstance(earnings_date, str):
            # String format - parse it
            earnings_date = parser.parse(earnings_date).date()
        elif not isinstance(earnings_date, date):
            # Unknown format
            return False

        # Compare to today and tomorrow
        today = utcnow().date()
        tomorrow = today + timedelta(days=1)

        if earnings_date in (today, tomorrow):
            logger.info(f"{symbol}: earnings on {earnings_date} (imminent)")
            return True

        logger.debug(f"{symbol}: earnings on {earnings_date} (not imminent)")
        return False

    except Exception as e:
        # Fail-open: if check fails, don't block the trade
        logger.debug(f"{symbol}: earnings check failed ({e.__class__.__name__}), proceeding normally")
        return False


def clear_cache():
    """Clear the earnings cache (called daily at cycle start)."""
    global _earnings_cache
    _earnings_cache = {}
    logger.debug("Earnings cache cleared")
