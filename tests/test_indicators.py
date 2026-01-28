import pytest
import pandas as pd
import numpy as np
from src.analysis.indicators import calculate_indicators, get_technical_alignment_score


def make_test_df(rows=100):
    """Generate test OHLCV data."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")
    close = 100 + np.cumsum(np.random.randn(rows) * 2)
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


def test_calculate_indicators():
    df = make_test_df()
    result = calculate_indicators(df)
    assert result is not None
    assert 0 <= result.rsi <= 100
    assert result.rsi_signal in ("oversold", "neutral", "overbought")
    assert result.macd_trend in ("bullish", "bearish", "neutral")


def test_calculate_indicators_insufficient_data():
    df = make_test_df(rows=20)
    result = calculate_indicators(df)
    assert result is None


def test_technical_alignment_score():
    df = make_test_df()
    indicators = calculate_indicators(df)
    score = get_technical_alignment_score(indicators, "buy")
    assert 0 <= score <= 100


def test_technical_alignment_score_sell():
    df = make_test_df()
    indicators = calculate_indicators(df)
    score = get_technical_alignment_score(indicators, "sell")
    assert 0 <= score <= 100
