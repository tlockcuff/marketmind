"""Daily equity snapshots for performance tracking."""

import logging
import os
from datetime import datetime, date
from typing import Optional

from src.db import get_db
from src.trading.alpaca_client import AlpacaClient
from src.analysis.market_data import MarketDataFetcher
from src.utils import utcnow

logger = logging.getLogger(__name__)


def _mode() -> str:
    return "live" if os.environ.get("TRADING_MODE", "paper").lower() == "live" else "paper"


def get_benchmark_prices() -> dict:
    """Fetch SPY and BTC-USD close prices for benchmark comparison."""
    market_data = MarketDataFetcher()
    benchmarks = {}
    
    # Get SPY close price
    try:
        spy_quote = market_data.get_quote("SPY")
        if spy_quote and spy_quote.get("price"):
            benchmarks["spy_close"] = float(spy_quote["price"])
    except Exception as e:
        logger.warning(f"Failed to fetch SPY price: {e}")
        benchmarks["spy_close"] = None

    # Get BTC/USD close price  
    try:
        btc_quote = market_data.get_quote("BTC/USD")
        if btc_quote and btc_quote.get("price"):
            benchmarks["btcusd_close"] = float(btc_quote["price"])
    except Exception as e:
        logger.warning(f"Failed to fetch BTC/USD price: {e}")
        benchmarks["btcusd_close"] = None
    
    return benchmarks


def calculate_day_pnl(snapshot_date: date) -> float:
    """Calculate P/L from trades closed today."""
    mode = _mode()
    try:
        with get_db() as conn:
            result = conn.execute(
                """SELECT COALESCE(SUM(pnl), 0) 
                   FROM trades 
                   WHERE mode = %s 
                   AND status != 'open' 
                   AND exit_time::date = %s""",
                (mode, snapshot_date)
            ).fetchone()
            return float(result[0]) if result else 0.0
    except Exception as e:
        logger.warning(f"Failed to calculate day P/L: {e}")
        return 0.0


def calculate_cumulative_pnl() -> float:
    """Calculate cumulative P/L from all closed trades."""
    mode = _mode()
    try:
        with get_db() as conn:
            result = conn.execute(
                """SELECT COALESCE(SUM(pnl), 0) 
                   FROM trades 
                   WHERE mode = %s 
                   AND status != 'open'""",
                (mode,)
            ).fetchone()
            return float(result[0]) if result else 0.0
    except Exception as e:
        logger.warning(f"Failed to calculate cumulative P/L: {e}")
        return 0.0


def count_open_positions() -> int:
    """Count current open positions."""
    mode = _mode()
    try:
        with get_db() as conn:
            result = conn.execute(
                """SELECT COUNT(*) 
                   FROM trades 
                   WHERE mode = %s 
                   AND status = 'open'""",
                (mode,)
            ).fetchone()
            return int(result[0]) if result else 0
    except Exception as e:
        logger.warning(f"Failed to count open positions: {e}")
        return 0


def take_snapshot(snapshot_date: Optional[date] = None) -> bool:
    """Take a daily snapshot of account performance and benchmarks.
    
    Args:
        snapshot_date: Date for the snapshot (defaults to today)
        
    Returns:
        True if successful, False otherwise
    """
    if snapshot_date is None:
        snapshot_date = utcnow().date()
    
    mode = _mode()
    logger.info(f"Taking daily snapshot for {snapshot_date} (mode: {mode})")
    
    try:
        # Get account information
        alpaca = AlpacaClient()
        account = alpaca.get_account()
        if not account:
            logger.error("Failed to get account info")
            return False
        
        equity = account.get("equity", 0)
        cash = account.get("cash", 0) 
        long_market_value = account.get("long_market_value", 0)
        short_market_value = account.get("short_market_value", 0)
        positions_value = long_market_value + abs(short_market_value)
        
        # Get open positions count
        open_positions = count_open_positions()
        
        # Calculate P/L metrics
        day_pnl = calculate_day_pnl(snapshot_date)
        cumulative_pnl = calculate_cumulative_pnl()
        
        # Get benchmark prices
        benchmarks = get_benchmark_prices()
        
        # Insert or update snapshot
        with get_db() as conn:
            conn.execute(
                """INSERT INTO daily_snapshots 
                   (mode, date, equity, cash, positions_value, open_positions, 
                    day_pnl, cumulative_pnl, spy_close, btcusd_close)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (mode, date) 
                   DO UPDATE SET 
                       equity = EXCLUDED.equity,
                       cash = EXCLUDED.cash,
                       positions_value = EXCLUDED.positions_value,
                       open_positions = EXCLUDED.open_positions,
                       day_pnl = EXCLUDED.day_pnl,
                       cumulative_pnl = EXCLUDED.cumulative_pnl,
                       spy_close = EXCLUDED.spy_close,
                       btcusd_close = EXCLUDED.btcusd_close,
                       created_at = NOW()""",
                (mode, snapshot_date, equity, cash, positions_value, open_positions,
                 day_pnl, cumulative_pnl, benchmarks.get("spy_close"), 
                 benchmarks.get("btcusd_close"))
            )
            conn.commit()
        
        logger.info(f"Daily snapshot saved: equity=${equity:,.2f}, day_pnl=${day_pnl:+,.2f}, positions={open_positions}")
        return True
        
    except Exception as e:
        logger.exception(f"Failed to take daily snapshot: {e}")
        return False


def get_recent_snapshots(days: int = 30) -> list:
    """Get recent daily snapshots for analysis."""
    mode = _mode()
    try:
        with get_db() as conn:
            rows = conn.execute(
                """SELECT date, equity, cash, positions_value, open_positions,
                          day_pnl, cumulative_pnl, spy_close, btcusd_close
                   FROM daily_snapshots 
                   WHERE mode = %s 
                   ORDER BY date DESC 
                   LIMIT %s""",
                (mode, days)
            ).fetchall()
            
            return [
                {
                    "date": r[0].isoformat(),
                    "equity": float(r[1]) if r[1] else 0,
                    "cash": float(r[2]) if r[2] else 0,
                    "positions_value": float(r[3]) if r[3] else 0,
                    "open_positions": r[4] or 0,
                    "day_pnl": float(r[5]) if r[5] else 0,
                    "cumulative_pnl": float(r[6]) if r[6] else 0,
                    "spy_close": float(r[7]) if r[7] else None,
                    "btcusd_close": float(r[8]) if r[8] else None,
                }
                for r in rows
            ]
    except Exception as e:
        logger.exception(f"Failed to get recent snapshots: {e}")
        return []