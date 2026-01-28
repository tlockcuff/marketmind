import pytest
import pandas as pd
import numpy as np
from src.analysis.backtester import backtest_signal, calculate_backtest_score


def make_test_df(rows=100, trend="up"):
    """Generate test OHLCV data."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")

    if trend == "up":
        close = 100 + np.cumsum(np.abs(np.random.randn(rows)) * 0.5)
    elif trend == "down":
        close = 100 - np.cumsum(np.abs(np.random.randn(rows)) * 0.5)
    else:
        close = 100 + np.cumsum(np.random.randn(rows) * 0.5)

    high = close + np.abs(np.random.randn(rows))
    low = close - np.abs(np.random.randn(rows))
    open_ = close + np.random.randn(rows) * 0.5
    volume = np.random.randint(1000000, 10000000, rows)

    return pd.DataFrame({
        "date": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def test_backtest_signal_buy():
    df = make_test_df(trend="up")
    result = backtest_signal(df, "buy")
    assert result is not None
    assert 0 <= result.win_rate <= 100
    assert result.total_trades > 0


def test_backtest_signal_sell():
    df = make_test_df(trend="down")
    result = backtest_signal(df, "sell")
    assert result is not None


def test_backtest_insufficient_data():
    df = make_test_df(rows=5)
    result = backtest_signal(df, "buy")
    assert result is None


def test_calculate_backtest_score():
    score = calculate_backtest_score(
        win_rate=60,
        avg_return=2.5,
        max_drawdown=5,
        sharpe=1.5,
    )
    assert 0 <= score <= 100
    assert score > 50  # Good metrics should score high
