"""Shared pytest fixtures — mock DB and external APIs so tests run offline."""

import os
import pytest
from unittest.mock import patch, MagicMock

# Ensure settings never hits a real database during import
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")


@pytest.fixture(autouse=True)
def _mock_db(monkeypatch):
    """Patch get_db globally so no test accidentally connects to PostgreSQL."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_conn.__enter__ = lambda self: self
    mock_conn.__exit__ = MagicMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.connection.return_value = mock_conn

    monkeypatch.setattr("src.db._pool", mock_pool)


@pytest.fixture
def mock_alpaca():
    """Patch AlpacaClient to avoid real API calls."""
    with patch("src.trading.alpaca_client.TradingClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_settings(monkeypatch):
    """Override settings.get() to return defaults without DB lookup."""
    import config.settings as cfg

    _defaults = {
        "scoring_weights": cfg.SCORING_WEIGHTS,
        "stop_loss_pct": cfg.STOP_LOSS_PCT,
        "take_profit_pct": cfg.TAKE_PROFIT_PCT,
        "max_position_pct": cfg.MAX_POSITION_PCT,
        "min_score_threshold": cfg.MIN_SCORE_THRESHOLD,
        "daily_loss_limit_pct": cfg.DAILY_LOSS_LIMIT_PCT,
        "max_concurrent_positions": cfg.MAX_CONCURRENT_POSITIONS,
        "scan_interval_minutes": cfg.SCAN_INTERVAL_MINUTES,
    }

    def mock_get(key):
        lower = key.lower()
        if lower in _defaults:
            return _defaults[lower]
        upper = key.upper()
        return getattr(cfg, upper, getattr(cfg, lower, None))

    monkeypatch.setattr(cfg, "get_config_overrides", lambda: {})
    monkeypatch.setattr(cfg, "get", mock_get)
