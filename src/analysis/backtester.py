import logging
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    win_rate: float
    avg_return: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    profitable_trades: int
    score: float  # 0-100


def backtest_signal(
    df: pd.DataFrame,
    direction: str,
    entry_condition: str = "close",
    hold_days: int = 5,
    stop_loss_pct: float = None,
    take_profit_pct: float = None,
) -> Optional[BacktestResult]:
    """
    Backtest a simple signal on historical data.
    Simulates entering at each bar and holding for N days.
    """
    if df is None or len(df) < hold_days + 10:
        return None

    logger.info(f"Running backtest ({len(df)} bars, {hold_days}d hold, {direction})...")
    stop_loss_pct = stop_loss_pct or settings.STOP_LOSS_PCT
    take_profit_pct = take_profit_pct or settings.TAKE_PROFIT_PCT

    df = df.copy().reset_index(drop=True)
    returns = []

    # Simulate trades at each point (except last hold_days)
    for i in range(len(df) - hold_days - 1):
        entry_price = df.loc[i, "close"]

        # Track through holding period
        exit_price = entry_price
        for j in range(1, hold_days + 1):
            if i + j >= len(df):
                break

            high = df.loc[i + j, "high"]
            low = df.loc[i + j, "low"]
            close = df.loc[i + j, "close"]

            if direction in ("buy", "long"):
                # Check stop loss
                if (entry_price - low) / entry_price >= stop_loss_pct:
                    exit_price = entry_price * (1 - stop_loss_pct)
                    break
                # Check take profit
                if (high - entry_price) / entry_price >= take_profit_pct:
                    exit_price = entry_price * (1 + take_profit_pct)
                    break
                exit_price = close
            else:
                # Short position
                if (high - entry_price) / entry_price >= stop_loss_pct:
                    exit_price = entry_price * (1 + stop_loss_pct)
                    break
                if (entry_price - low) / entry_price >= take_profit_pct:
                    exit_price = entry_price * (1 - take_profit_pct)
                    break
                exit_price = close

        # Calculate return
        if direction in ("buy", "long"):
            ret = (exit_price - entry_price) / entry_price
        else:
            ret = (entry_price - exit_price) / entry_price
        returns.append(ret)

    if not returns:
        return None

    returns = np.array(returns)
    profitable = returns > 0
    win_rate = np.mean(profitable) * 100
    avg_return = np.mean(returns) * 100

    # Max drawdown
    cumulative = np.cumprod(1 + returns)
    rolling_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - rolling_max) / rolling_max
    max_drawdown = abs(np.min(drawdowns)) * 100

    # Sharpe ratio (annualized, assuming daily)
    if np.std(returns) > 0:
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
    else:
        sharpe = 0

    # Score calculation
    score = calculate_backtest_score(win_rate, avg_return, max_drawdown, sharpe)

    logger.info(f"Backtest done: {win_rate:.0f}% WR, {avg_return:.1f}% avg ret, sharpe={sharpe:.2f}, score={score}")
    return BacktestResult(
        win_rate=win_rate,
        avg_return=avg_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe,
        total_trades=len(returns),
        profitable_trades=int(np.sum(profitable)),
        score=score,
    )


def calculate_backtest_score(
    win_rate: float,
    avg_return: float,
    max_drawdown: float,
    sharpe: float,
) -> float:
    """Convert backtest metrics to 0-100 score."""
    score = 0

    # Win rate contribution (0-30 points)
    if win_rate >= 60:
        score += 30
    elif win_rate >= 50:
        score += 20
    elif win_rate >= 40:
        score += 10

    # Average return contribution (0-30 points)
    if avg_return >= 2:
        score += 30
    elif avg_return >= 1:
        score += 20
    elif avg_return >= 0:
        score += 10
    elif avg_return >= -1:
        score += 5

    # Max drawdown penalty (0-20 points)
    if max_drawdown <= 5:
        score += 20
    elif max_drawdown <= 10:
        score += 15
    elif max_drawdown <= 15:
        score += 10
    elif max_drawdown <= 20:
        score += 5

    # Sharpe ratio contribution (0-20 points)
    if sharpe >= 2:
        score += 20
    elif sharpe >= 1:
        score += 15
    elif sharpe >= 0.5:
        score += 10
    elif sharpe >= 0:
        score += 5

    return min(100, max(0, score))
