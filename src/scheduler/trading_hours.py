import logging
from datetime import datetime, time
from typing import Optional
import pytz

from config import settings
from config.holidays import MARKET_HOLIDAYS, EARLY_CLOSE_DAYS

logger = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")

MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)


def is_24_7_mode() -> bool:
    """Check if 24/7 paper trading mode is enabled."""
    return getattr(settings, 'PAPER_TRADING_24_7', False)


def now_et() -> datetime:
    """Get current time in Eastern."""
    return datetime.now(ET)


def is_market_open() -> bool:
    """Check if market is currently open (or 24/7 mode)."""
    # 24/7 paper trading mode - always open
    if is_24_7_mode():
        return True

    now = now_et()

    # Check weekend
    if now.weekday() >= 5:
        return False

    # Check holiday
    if now.date() in MARKET_HOLIDAYS:
        return False

    # Check time
    current_time = now.time()
    close_time = EARLY_CLOSE if now.date() in EARLY_CLOSE_DAYS else MARKET_CLOSE

    return MARKET_OPEN <= current_time < close_time


def is_trading_day() -> bool:
    """Check if today is a trading day (or 24/7 mode)."""
    if is_24_7_mode():
        return True

    now = now_et()
    if now.weekday() >= 5:
        return False
    if now.date() in MARKET_HOLIDAYS:
        return False
    return True


def time_until_open() -> Optional[int]:
    """Seconds until market opens. None if open or weekend/holiday."""
    if not is_trading_day():
        return None

    now = now_et()
    if now.time() >= MARKET_OPEN:
        return None  # Already open or past open

    market_open_dt = now.replace(
        hour=MARKET_OPEN.hour,
        minute=MARKET_OPEN.minute,
        second=0,
        microsecond=0,
    )
    return int((market_open_dt - now).total_seconds())


def time_until_close() -> Optional[int]:
    """Seconds until market closes. None if closed."""
    if not is_market_open():
        return None

    now = now_et()
    close_time = EARLY_CLOSE if now.date() in EARLY_CLOSE_DAYS else MARKET_CLOSE

    market_close_dt = now.replace(
        hour=close_time.hour,
        minute=close_time.minute,
        second=0,
        microsecond=0,
    )
    return int((market_close_dt - now).total_seconds())


def should_avoid_trading() -> tuple[bool, str]:
    """Check conditions where trading should be avoided."""
    # 24/7 mode - no restrictions
    if is_24_7_mode():
        return False, ""

    now = now_et()

    # Avoid first 15 minutes (high volatility)
    first_15 = now.replace(hour=9, minute=45, second=0)
    if now.time() < first_15.time():
        return True, "First 15 minutes"

    # Avoid last 15 minutes (closing volatility)
    close_time = EARLY_CLOSE if now.date() in EARLY_CLOSE_DAYS else MARKET_CLOSE
    close_dt = now.replace(hour=close_time.hour, minute=close_time.minute)
    if (close_dt - now).total_seconds() < 900:
        return True, "Last 15 minutes"

    return False, ""


def get_next_market_open() -> datetime:
    """Get datetime of next market open."""
    now = now_et()

    # Start with today or tomorrow
    if now.time() >= MARKET_CLOSE or not is_trading_day():
        check_date = now.date()
    else:
        return now.replace(
            hour=MARKET_OPEN.hour,
            minute=MARKET_OPEN.minute,
            second=0,
            microsecond=0,
        )

    # Find next trading day
    from datetime import timedelta
    for i in range(1, 10):
        check = check_date + timedelta(days=i)
        if check.weekday() < 5 and check not in MARKET_HOLIDAYS:
            return ET.localize(datetime.combine(check, MARKET_OPEN))

    return None


def format_market_status() -> str:
    """Get human-readable market status."""
    if is_24_7_mode():
        return "24/7 Paper Trading"

    if is_market_open():
        seconds = time_until_close()
        if seconds:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"Market OPEN - closes in {hours}h {minutes}m"
        return "Market OPEN"
    elif is_trading_day():
        seconds = time_until_open()
        if seconds:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"Market CLOSED - opens in {hours}h {minutes}m"
        else:
            return "Market CLOSED for today"
    else:
        next_open = get_next_market_open()
        if next_open:
            return f"Market CLOSED - next open: {next_open.strftime('%a %b %d %H:%M ET')}"
        return "Market CLOSED"
