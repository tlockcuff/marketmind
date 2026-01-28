import os
from dotenv import load_dotenv

load_dotenv();

# Trading mode: "paper" or "live"
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()

# API Keys - Grok
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1")

# API Keys - Alpaca (separate keys for paper/live)
ALPACA_PAPER_API_KEY = os.getenv("ALPACA_PAPER_API_KEY", os.getenv("ALPACA_API_KEY"))
ALPACA_PAPER_SECRET_KEY = os.getenv("ALPACA_PAPER_SECRET_KEY", os.getenv("ALPACA_SECRET_KEY"))
ALPACA_LIVE_API_KEY = os.getenv("ALPACA_LIVE_API_KEY")
ALPACA_LIVE_SECRET_KEY = os.getenv("ALPACA_LIVE_SECRET_KEY")

# Select active keys based on mode
if TRADING_MODE == "live":
    ALPACA_API_KEY = ALPACA_LIVE_API_KEY
    ALPACA_SECRET_KEY = ALPACA_LIVE_SECRET_KEY
    ALPACA_BASE_URL = "https://api.alpaca.markets"
else:
    ALPACA_API_KEY = ALPACA_PAPER_API_KEY
    ALPACA_SECRET_KEY = ALPACA_PAPER_SECRET_KEY
    ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Portfolio
PAPER_PORTFOLIO_SIZE = 100_000 # 100,000 paper portfolio size

# Risk parameters
MAX_POSITION_PCT = 0.15 # 15% of equity per trade
MAX_CONCURRENT_POSITIONS = 20 # 20 concurrent positions
STOP_LOSS_PCT = 0.05 # 5% stop loss
TAKE_PROFIT_PCT = 0.12 # 12% take profit
DAILY_LOSS_LIMIT_PCT = 0.10 # 10% daily loss limit
MIN_SCORE_THRESHOLD = 65 # 65% minimum score to trade   
SCAN_INTERVAL_MINUTES = 5 # 5 minutes between scans

# Scoring weights
SCORING_WEIGHTS = {
    "grok_confidence": 0.20, # 20% weight for Grok confidence
    "technical_alignment": 0.30, # 30% weight for technical alignment
    "backtest_performance": 0.20, # 20% weight for backtest performance
    "volume_momentum": 0.15, # 15% weight for volume momentum
    "risk_reward": 0.15, # 15% weight for risk/reward
}

# Time-based exits
MAX_HOLD_HOURS = 48  # Force close after this hours
STALE_POSITION_HOURS = 24  # Tighten stop to breakeven + 0.5%

# Backtest
BACKTEST_DAYS = 90 # 90 days of backtest data

# Minimum hold time before Grok can exit a position
MIN_HOLD_MINUTES = 30 # 30 minutes minimum hold time

# Trading mode
ALLOW_SHORT_SELLING = True # Allow short selling
PAPER_TRADING_24_7 = TRADING_MODE == "paper"  # 24/7 only for paper

# Day trade limits (PDT rule for accounts < $25k)
# A day trade = buy AND sell same stock same day
DAY_TRADE_LIMIT = 3  # Max day trades per 5-day rolling window (PDT rule)
PDT_EQUITY_THRESHOLD = 25_000  # Accounts above this are exempt from PDT
MIN_SCORE_FOR_DAY_TRADE = 80  # Only day trade high-confidence signals
RESERVE_DAY_TRADES = 1  # Always keep 1 day trade for emergencies

# Options trading
OPTIONS_ENABLED = True # Enable options trading
OPTIONS_MAX_POSITION_PCT = 0.02       # 2% equity per options trade
OPTIONS_MIN_SCORE_DIRECTIONAL = 65 # 65% minimum score for directional options
OPTIONS_MIN_SCORE_SPREAD = 80 # 80% minimum score for spread options
OPTIONS_PROFIT_TARGET_DIRECTIONAL = 0.50 # 50% profit target for directional options
OPTIONS_STOP_LOSS_DIRECTIONAL = 0.50 # 50% stop loss for directional options
OPTIONS_PROFIT_TARGET_SPREAD = 0.50   # close at 50% max profit
OPTIONS_DTE_MIN = 7 # 7 days minimum DTE
OPTIONS_DTE_MAX = 21 # 21 days maximum DTE
OPTIONS_DTE_MAX_SPREAD = 30 # 30 days maximum spread DTE
OPTIONS_DTE_EXIT = 2 # 2 days minimum DTE exit
OPTIONS_MAX_CONCURRENT = 10            # separate from stock limit
OPTIONS_DELTA_RANGE = (0.30, 0.50) # 30% minimum delta range
OPTIONS_CC_DELTA_RANGE = (0.20, 0.30) # 20% minimum delta range for covered calls
OPTIONS_MIN_OPEN_INTEREST = 100 # 100 minimum open interest
OPTIONS_MAX_SPREAD_PCT = 0.10 # 10% maximum spread percentage
COVERED_CALL_MIN_PROFIT_PCT = 0.02 # 2% minimum profit percentage for covered calls
COVERED_CALL_MIN_PREMIUM_PCT = 0.005 # 0.5% minimum premium percentage for covered calls

# Congressional trading data
CONGRESS_ENABLED = os.getenv("CONGRESS_ENABLED", "true").lower() == "true"
CONGRESS_CACHE_TTL_HOURS = 6 # 6 hours cache ttl
CONGRESS_LOOKBACK_DAYS = 30 # 30 days lookback

def is_paper_mode() -> bool:
    return TRADING_MODE == "paper"

def is_live_mode() -> bool:
    return TRADING_MODE == "live"
