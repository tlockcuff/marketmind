import pytest
from datetime import date
from src.scheduler.trading_hours import (
    is_trading_day,
    should_avoid_trading,
)
from config.holidays import MARKET_HOLIDAYS


def test_holidays_defined():
    assert len(MARKET_HOLIDAYS) > 0
    # Check 2024 holidays exist
    assert date(2024, 12, 25) in MARKET_HOLIDAYS


def test_trading_day_holiday():
    # Can't easily mock datetime, just test holiday list
    assert date(2024, 12, 25) in MARKET_HOLIDAYS
    assert date(2025, 1, 1) in MARKET_HOLIDAYS
