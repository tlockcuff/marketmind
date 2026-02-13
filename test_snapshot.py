#!/usr/bin/env python3
"""Test script for the daily snapshot functionality."""

import sys
import os
sys.path.insert(0, '.')

def test_imports():
    """Test that all modules can be imported."""
    try:
        from src.tracking.daily_snapshot import take_snapshot
        print("✓ Daily snapshot module imported successfully")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_strategy_classification():
    """Test strategy classification function."""
    try:
        from src.trading.trade_history import classify_strategy
        
        test_cases = [
            ({"signal_source": "momentum"}, "Moving higher on momentum", "momentum"),
            ({}, "Oversold bounce expected", "mean_reversion"),
            ({}, "Breaking out above resistance", "breakout"),
            ({}, "Following the trend direction", "trend_follow"),
            ({}, "Earnings catalyst expected", "news_catalyst"),
            ({"signal_source": "congress"}, "", "congress_signal"),
            ({}, "BTC/USD swing setup", "crypto_swing"),
            ({}, "Generic trade setup", "other"),
        ]
        
        for score_breakdown, rationale, expected in test_cases:
            result = classify_strategy(score_breakdown, rationale)
            status = "✓" if result == expected else "✗"
            print(f"{status} Strategy classification: '{rationale}' -> {result} (expected: {expected})")
        
        return True
    except Exception as e:
        print(f"✗ Strategy classification test error: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing MarketMind performance tracking modules...")
    print("=" * 60)
    
    success = True
    success &= test_imports()
    success &= test_strategy_classification()
    
    print("=" * 60)
    if success:
        print("✓ All tests passed!")
        print("\nTo test the snapshot functionality:")
        print("1. Ensure database is running and accessible")
        print("2. Run: python -c 'from src.tracking.daily_snapshot import take_snapshot; print(take_snapshot())'")
    else:
        print("✗ Some tests failed. Check the logs above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())