import pytest
from src.signals.signal_parser import parse_grok_response, parse_json_signals


def test_parse_grok_response_buy():
    text = "Buy AAPL at $185 with 75% confidence. Stop loss at $180, target $195."
    signals = parse_grok_response(text)
    assert len(signals) >= 1
    assert signals[0].ticker == "AAPL"
    assert signals[0].direction == "buy"


def test_parse_grok_response_sell():
    text = "Short TSLA, bearish momentum. 60% confidence."
    signals = parse_grok_response(text)
    assert len(signals) >= 1
    assert signals[0].direction == "sell"


def test_parse_json_signals():
    data = {
        "signals": [
            {
                "ticker": "NVDA",
                "direction": "buy",
                "confidence": 80,
                "entry_price": 500,
                "stop_loss": 485,
                "take_profit": 530,
                "rationale": "Breaking out",
            }
        ]
    }
    signals = parse_json_signals(data)
    assert len(signals) == 1
    assert signals[0].ticker == "NVDA"
    assert signals[0].confidence == 80


def test_parse_json_signals_list():
    data = [
        {"ticker": "MSFT", "direction": "buy", "confidence": 70},
        {"ticker": "GOOG", "direction": "sell", "confidence": 65},
    ]
    signals = parse_json_signals(data)
    assert len(signals) == 2
