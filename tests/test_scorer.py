import pytest
from src.analysis.scorer import (
    calculate_trade_score,
    calculate_volume_score,
    calculate_risk_reward_score,
    get_position_size_multiplier,
)


def test_calculate_trade_score_high():
    score = calculate_trade_score(
        grok_confidence=90,
        indicators=None,
        backtest=None,
        direction="buy",
        current_volume=2000000,
        avg_volume=1000000,
    )
    assert score.total_score > 50


def test_calculate_trade_score_action():
    score = calculate_trade_score(
        grok_confidence=85,
        indicators=None,
        backtest=None,
        direction="buy",
    )
    assert score.action in ("strong_buy", "buy", "hold", "weak", "avoid")


def test_volume_score_high():
    score = calculate_volume_score(3000000, 1000000)
    assert score >= 80


def test_volume_score_low():
    score = calculate_volume_score(300000, 1000000)
    assert score <= 50


def test_volume_score_missing():
    score = calculate_volume_score(None, None)
    assert score == 50


def test_risk_reward_score():
    score = calculate_risk_reward_score(
        entry_price=100,
        stop_loss=97,
        take_profit=108,
        direction="buy",
    )
    # R:R = 8/3 = 2.67, should score well
    assert score >= 70


def test_position_size_multiplier():
    assert get_position_size_multiplier(90) == 1.0
    assert get_position_size_multiplier(80) == 0.8
    assert get_position_size_multiplier(70) == 0.5
    assert get_position_size_multiplier(50) == 0.0
