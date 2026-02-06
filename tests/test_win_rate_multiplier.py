"""Test win rate multiplier logic."""
import pytest
from unittest.mock import MagicMock, patch
from src.trading.risk_mgr import RiskManager


def test_win_rate_multiplier_insufficient_data():
    """Should return 1.0 when fewer than 5 closed trades."""
    risk_mgr = RiskManager()

    # Mock DB to return fewer than 5 trades
    with patch('src.trading.risk_mgr.get_db') as mock_db:
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            (10.0,),
            (5.0,),
            (-3.0,),
        ]
        mock_db.return_value.__enter__.return_value = mock_conn

        multiplier = risk_mgr.get_win_rate_multiplier()
        assert multiplier == 1.0


def test_win_rate_multiplier_cold_streak():
    """Should return 0.50 when win rate < 40%."""
    risk_mgr = RiskManager()

    # Mock DB to return 20 trades with 30% win rate (6 wins, 14 losses)
    with patch('src.trading.risk_mgr.get_db') as mock_db:
        mock_conn = MagicMock()
        trades = [(10.0,)] * 6 + [(-5.0,)] * 14  # 6 wins, 14 losses
        mock_conn.execute.return_value.fetchall.return_value = trades
        mock_db.return_value.__enter__.return_value = mock_conn

        multiplier = risk_mgr.get_win_rate_multiplier()
        assert multiplier == 0.50


def test_win_rate_multiplier_hot_streak():
    """Should return 1.25 when win rate > 60%."""
    risk_mgr = RiskManager()

    # Mock DB to return 20 trades with 70% win rate (14 wins, 6 losses)
    with patch('src.trading.risk_mgr.get_db') as mock_db:
        mock_conn = MagicMock()
        trades = [(10.0,)] * 14 + [(-5.0,)] * 6  # 14 wins, 6 losses
        mock_conn.execute.return_value.fetchall.return_value = trades
        mock_db.return_value.__enter__.return_value = mock_conn

        multiplier = risk_mgr.get_win_rate_multiplier()
        assert multiplier == 1.25


def test_win_rate_multiplier_normal():
    """Should return 1.0 when win rate is between 40-60%."""
    risk_mgr = RiskManager()

    # Mock DB to return 20 trades with 50% win rate (10 wins, 10 losses)
    with patch('src.trading.risk_mgr.get_db') as mock_db:
        mock_conn = MagicMock()
        trades = [(10.0,)] * 10 + [(-5.0,)] * 10  # 10 wins, 10 losses
        mock_conn.execute.return_value.fetchall.return_value = trades
        mock_db.return_value.__enter__.return_value = mock_conn

        multiplier = risk_mgr.get_win_rate_multiplier()
        assert multiplier == 1.0


def test_win_rate_multiplier_db_error():
    """Should return 1.0 on DB error (fail-open)."""
    risk_mgr = RiskManager()

    # Mock DB to raise exception
    with patch('src.trading.risk_mgr.get_db') as mock_db:
        mock_db.side_effect = Exception("DB connection failed")

        multiplier = risk_mgr.get_win_rate_multiplier()
        assert multiplier == 1.0
