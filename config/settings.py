import json
import os
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv();

# Trading mode: "paper" or "live"
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()

# API Keys - Grok
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_BASE_URL = os.getenv("GROK_BASE_URL", "https://api.x.ai/v1")

# API Keys - Alpaca
# Env vars are fallback; primary source is the alpaca_keys DB table (managed via web UI)
ALPACA_PAPER_API_KEY = os.getenv("ALPACA_PAPER_API_KEY", os.getenv("ALPACA_API_KEY"))
ALPACA_PAPER_SECRET_KEY = os.getenv("ALPACA_PAPER_SECRET_KEY", os.getenv("ALPACA_SECRET_KEY"))
ALPACA_LIVE_API_KEY = os.getenv("ALPACA_LIVE_API_KEY")
ALPACA_LIVE_SECRET_KEY = os.getenv("ALPACA_LIVE_SECRET_KEY")

def _load_alpaca_keys_from_db():
    """Load Alpaca keys from DB. Returns (api_key, secret_key) or (None, None)."""
    try:
        from src.db import get_db
        with get_db() as conn:
            row = conn.execute("SELECT api_key, secret_key FROM alpaca_keys WHERE id = 1").fetchone()
            if row:
                return row[0], row[1]
    except Exception:
        pass
    return None, None

def _resolve_alpaca_keys():
    """Resolve Alpaca keys: DB first, then env vars."""
    global ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL
    global ALPACA_PAPER_API_KEY, ALPACA_PAPER_SECRET_KEY
    global ALPACA_LIVE_API_KEY, ALPACA_LIVE_SECRET_KEY

    db_api, db_secret = _load_alpaca_keys_from_db()
    if db_api and db_secret:
        ALPACA_API_KEY = db_api
        ALPACA_SECRET_KEY = db_secret
        if TRADING_MODE == "live":
            ALPACA_LIVE_API_KEY = db_api
            ALPACA_LIVE_SECRET_KEY = db_secret
        else:
            ALPACA_PAPER_API_KEY = db_api
            ALPACA_PAPER_SECRET_KEY = db_secret
    elif TRADING_MODE == "live":
        ALPACA_API_KEY = ALPACA_LIVE_API_KEY
        ALPACA_SECRET_KEY = ALPACA_LIVE_SECRET_KEY
    else:
        ALPACA_API_KEY = ALPACA_PAPER_API_KEY
        ALPACA_SECRET_KEY = ALPACA_PAPER_SECRET_KEY

    ALPACA_BASE_URL = "https://api.alpaca.markets" if TRADING_MODE == "live" else "https://paper-api.alpaca.markets"

# Select active keys based on mode (env fallback)
if TRADING_MODE == "live":
    ALPACA_API_KEY = ALPACA_LIVE_API_KEY
    ALPACA_SECRET_KEY = ALPACA_LIVE_SECRET_KEY
    ALPACA_BASE_URL = "https://api.alpaca.markets"
else:
    ALPACA_API_KEY = ALPACA_PAPER_API_KEY
    ALPACA_SECRET_KEY = ALPACA_PAPER_SECRET_KEY
    ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

# Try loading from DB (may fail on first run before init_db)
_resolve_alpaca_keys()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Portfolio
PAPER_PORTFOLIO_SIZE = 100_000 # 100,000 paper portfolio size

# Risk parameters
MAX_POSITION_PCT = 0.12 # 12% of equity per trade (reduced from 25% for safety)
MAX_CONCURRENT_POSITIONS = 15 # 15 concurrent stock positions
STOP_LOSS_PCT = 0.045 # 4.5% stop loss (fallback when ATR unavailable; 3% causes premature stop-outs)
TAKE_PROFIT_PCT = 0.15 # 15% take profit (let winners run)
DAILY_LOSS_LIMIT_PCT = 0.08 # 8% daily loss limit (protects against catastrophic drawdowns)
MIN_SCORE_THRESHOLD = 65 # 65% minimum score to trade (raised from 50 for quality)
SCAN_INTERVAL_MINUTES = 5 # 5 minutes between scans

# Recovery mode — close worst losers when buying power too low
RECOVERY_BUYING_POWER_PCT = 0.10    # recover to 10% of equity free
RECOVERY_BUYING_POWER_MIN = 10000   # ...or $10000, whichever
RECOVERY_COOLDOWN_MINUTES = 5       # cooldown after recovery

# Scoring weights
SCORING_WEIGHTS = {
    "grok_confidence": 0.20, # 20% weight for Grok confidence
    "technical_alignment": 0.20, # 20% weight for technical alignment
    "mtf_alignment": 0.10, # 10% weight for multi-timeframe alignment
    "backtest_performance": 0.20, # 20% weight for backtest performance
    "volume_momentum": 0.15, # 15% weight for volume momentum
    "risk_reward": 0.15, # 15% weight for risk/reward
}

# Time-based exits
MAX_HOLD_HOURS = 24  # Force close after this hours
STALE_POSITION_HOURS = 10  # Tighten stop to breakeven + 0.5% (well before 24h force-close)

# Backtest
BACKTEST_DAYS = 90 # 90 days of backtest data

# Minimum hold time before Grok can exit a position
MIN_HOLD_MINUTES = 10 # 10 minutes minimum hold time

# Trading mode
ALLOW_SHORT_SELLING = True # Allow short selling
PAPER_TRADING_24_7 = TRADING_MODE == "paper"  # 24/7 only for paper

# Day trade limits (PDT rule for accounts < $25k)
# A day trade = buy AND sell same stock same day
DAY_TRADE_LIMIT = 3  # Max day trades per 5-day rolling window (PDT rule)
PDT_EQUITY_THRESHOLD = 25_000  # Accounts above this are exempt from PDT
MIN_SCORE_FOR_DAY_TRADE = 60  # Day trade more freely
RESERVE_DAY_TRADES = 1  # Always keep 1 day trade for emergencies

# Options trading
OPTIONS_ENABLED = True # Enable options trading
OPTIONS_MAX_POSITION_PCT = 0.05       # 5% equity per options trade
OPTIONS_MIN_SCORE_DIRECTIONAL = 70 # 70% minimum score for directional options (higher than stocks — leverage needs conviction)
OPTIONS_MIN_SCORE_SPREAD = 80 # 80% minimum score for spread options
OPTIONS_PROFIT_TARGET_DIRECTIONAL = 0.50 # 50% profit target for directional options
OPTIONS_STOP_LOSS_DIRECTIONAL = 0.50 # 50% stop loss for directional options
OPTIONS_PROFIT_TARGET_SPREAD = 0.50   # close at 50% max profit
OPTIONS_DTE_MIN = 1 # 0DTE disabled by default (extreme gamma risk)
OPTIONS_DTE_MAX = 14 # 14 days maximum DTE (shorter = more leverage)
OPTIONS_DTE_MAX_SPREAD = 30 # 30 days maximum spread DTE
OPTIONS_DTE_EXIT = 2 # 2 days minimum DTE exit
OPTIONS_MAX_CONCURRENT = 10            # separate from stock limit (reduced from 20)
OPTIONS_DELTA_RANGE = (0.40, 0.70) # wider delta range for more leverage
OPTIONS_CC_DELTA_RANGE = (0.20, 0.30) # 20% minimum delta range for covered calls
OPTIONS_MIN_OPEN_INTEREST = 100 # 100 minimum open interest
OPTIONS_MAX_SPREAD_PCT = 0.10 # 10% maximum spread percentage
COVERED_CALL_MIN_PROFIT_PCT = 0.02 # 2% minimum profit percentage for covered calls
COVERED_CALL_MIN_PREMIUM_PCT = 0.005 # 0.5% minimum premium percentage for covered calls

# Congressional trading data
CONGRESS_ENABLED = os.getenv("CONGRESS_ENABLED", "false").lower() == "true"
CONGRESS_CACHE_TTL_HOURS = 6 # 6 hours cache ttl
CONGRESS_LOOKBACK_DAYS = 30 # 30 days lookback

# News Sentinel — real-time headline monitor
NEWS_SENTINEL_ENABLED = os.getenv("NEWS_SENTINEL_ENABLED", "true").lower() == "true"
NEWS_SENTINEL_INTERVAL = int(os.getenv("NEWS_SENTINEL_INTERVAL", "60"))  # seconds
NEWS_SENTINEL_USE_GROK = os.getenv("NEWS_SENTINEL_USE_GROK", "false").lower() == "true"

# Daily P/L target (set via env, CLI --target, or web API)
DAILY_TARGET = float(os.getenv("DAILY_TARGET", "0")) or None  # e.g. 1000 = $1000 target

def get_daily_target() -> Optional[float]:
    """Get daily target from DB or settings."""
    try:
        from src.db import get_db
        with get_db() as conn:
            row = conn.execute("SELECT target FROM daily_target WHERE id = 1").fetchone()
            if row and row[0] is not None:
                return float(row[0])
    except Exception:
        pass
    return DAILY_TARGET

def set_daily_target(target: Optional[float]):
    """Persist daily target to DB."""
    try:
        from src.db import get_db
        with get_db() as conn:
            conn.execute(
                """INSERT INTO daily_target (id, target) VALUES (1, %s)
                   ON CONFLICT (id) DO UPDATE SET target = EXCLUDED.target""",
                (target,),
            )
            conn.commit()
    except Exception:
        pass

def is_paper_mode() -> bool:
    return TRADING_MODE == "paper"

def is_live_mode() -> bool:
    return TRADING_MODE == "live"

# ---------------------------------------------------------------------------
# Live-editable config override system
# ---------------------------------------------------------------------------

EDITABLE_SETTINGS = {
    # Risk
    "max_position_pct":          {"type": "float", "min": 0.01, "max": 1.0,  "label": "Max Position %",         "section": "Risk"},
    "stop_loss_pct":             {"type": "float", "min": 0.005,"max": 0.5,  "label": "Stop Loss %",            "section": "Risk"},
    "take_profit_pct":           {"type": "float", "min": 0.01, "max": 1.0,  "label": "Take Profit %",          "section": "Risk"},
    "daily_loss_limit_pct":      {"type": "float", "min": 0.01, "max": 1.0,  "label": "Daily Loss Limit %",     "section": "Risk"},
    "max_concurrent_positions":  {"type": "int",   "min": 1,    "max": 100,  "label": "Max Positions",           "section": "Risk"},
    # Trading
    "min_score_threshold":       {"type": "int",   "min": 1,    "max": 100,  "label": "Min Score",               "section": "Trading"},
    "scan_interval_minutes":     {"type": "int",   "min": 1,    "max": 60,   "label": "Scan Interval (min)",     "section": "Trading"},
    "max_hold_hours":            {"type": "int",   "min": 1,    "max": 168,  "label": "Max Hold Hours",          "section": "Trading"},
    "stale_position_hours":      {"type": "int",   "min": 1,    "max": 168,  "label": "Stale Position Hours",    "section": "Trading"},
    "allow_short_selling":       {"type": "bool",                             "label": "Allow Short Selling",     "section": "Trading"},
    "backtest_days":             {"type": "int",   "min": 7,    "max": 365,  "label": "Backtest Days",           "section": "Trading"},
    "min_hold_minutes":          {"type": "int",   "min": 0,    "max": 120,  "label": "Min Hold Minutes",        "section": "Trading"},
    # Day Trade
    "day_trade_limit":           {"type": "int",   "min": 0,    "max": 50,   "label": "Day Trade Limit",         "section": "Day Trade"},
    "min_score_for_day_trade":   {"type": "int",   "min": 1,    "max": 100,  "label": "Min Score Day Trade",     "section": "Day Trade"},
    "reserve_day_trades":        {"type": "int",   "min": 0,    "max": 10,   "label": "Reserve Day Trades",      "section": "Day Trade"},
    # Options
    "options_enabled":           {"type": "bool",                             "label": "Options Enabled",         "section": "Options"},
    "options_max_position_pct":  {"type": "float", "min": 0.01, "max": 0.5,  "label": "Options Max Position %",  "section": "Options"},
    "options_min_score_directional": {"type": "int", "min": 1,  "max": 100,  "label": "Options Min Score Dir",   "section": "Options"},
    "options_min_score_spread":  {"type": "int",   "min": 1,    "max": 100,  "label": "Options Min Score Spread","section": "Options"},
    "options_dte_min":           {"type": "int",   "min": 0,    "max": 30,   "label": "Options DTE Min",         "section": "Options"},
    "options_dte_max":           {"type": "int",   "min": 1,    "max": 90,   "label": "Options DTE Max",         "section": "Options"},
    "options_max_concurrent":    {"type": "int",   "min": 1,    "max": 100,  "label": "Options Max Concurrent",  "section": "Options"},
    # Recovery
    "recovery_buying_power_pct": {"type": "float", "min": 0.01, "max": 0.5,  "label": "Recovery BP %",           "section": "Recovery"},
    "recovery_buying_power_min": {"type": "float", "min": 100,  "max": 100000,"label": "Recovery BP Min $",      "section": "Recovery"},
    "recovery_cooldown_minutes": {"type": "int",   "min": 0,    "max": 60,   "label": "Recovery Cooldown (min)", "section": "Recovery"},
    # Data Sources
    "congress_enabled":          {"type": "bool",                             "label": "Congress Trading",        "section": "Data Sources"},
    # News Sentinel
    "news_sentinel_enabled":     {"type": "bool",                             "label": "News Sentinel",           "section": "Data Sources"},
    "news_sentinel_interval":    {"type": "int",   "min": 10,   "max": 300,  "label": "Sentinel Interval (s)",   "section": "Data Sources"},
    "news_sentinel_use_grok":    {"type": "bool",                             "label": "Sentinel Use Grok",       "section": "Data Sources"},
}


def get_config_overrides() -> dict:
    """Read overrides from DB."""
    try:
        from src.db import get_db
        with get_db() as conn:
            rows = conn.execute("SELECT key, value FROM config_overrides").fetchall()
            result = {}
            for r in rows:
                val = r[1]
                # JSONB wraps scalars, unwrap them
                if isinstance(val, dict) and "__val__" in val:
                    result[r[0]] = val["__val__"]
                else:
                    result[r[0]] = val
            return result
    except Exception:
        return {}


def set_config_overrides(overrides: dict):
    """Write overrides to DB. Merges with existing."""
    try:
        from src.db import get_db
        with get_db() as conn:
            for key, value in overrides.items():
                if value is None:
                    conn.execute("DELETE FROM config_overrides WHERE key = %s", (key,))
                else:
                    # Wrap non-dict values for JSONB storage
                    json_val = json.dumps({"__val__": value})
                    conn.execute(
                        """INSERT INTO config_overrides (key, value)
                           VALUES (%s, %s::jsonb)
                           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value""",
                        (key, json_val),
                    )
            conn.commit()
    except Exception:
        pass


def clear_config_overrides(keys: Optional[list] = None):
    """Clear all overrides or specific keys."""
    try:
        from src.db import get_db
        with get_db() as conn:
            if keys is None:
                conn.execute("DELETE FROM config_overrides")
            else:
                for k in keys:
                    conn.execute("DELETE FROM config_overrides WHERE key = %s", (k,))
            conn.commit()
    except Exception:
        pass


def get(key: str) -> Any:
    """Get setting value: override if set, else module constant."""
    overrides = get_config_overrides()
    lower_key = key.lower()
    if lower_key in overrides:
        return overrides[lower_key]
    # Fall back to module constant
    upper_key = key.upper()
    return globals().get(upper_key, globals().get(lower_key))


def validate_setting(key: str, value: Any) -> tuple[bool, str]:
    """Validate a setting value against EDITABLE_SETTINGS metadata."""
    meta = EDITABLE_SETTINGS.get(key)
    if not meta:
        return False, f"unknown setting: {key}"
    t = meta["type"]
    if t == "bool":
        if not isinstance(value, bool):
            return False, f"{key} must be boolean"
    elif t == "int":
        if not isinstance(value, (int, float)):
            return False, f"{key} must be numeric"
        value = int(value)
        if "min" in meta and value < meta["min"]:
            return False, f"{key} min is {meta['min']}"
        if "max" in meta and value > meta["max"]:
            return False, f"{key} max is {meta['max']}"
    elif t == "float":
        if not isinstance(value, (int, float)):
            return False, f"{key} must be numeric"
        value = float(value)
        if "min" in meta and value < meta["min"]:
            return False, f"{key} min is {meta['min']}"
        if "max" in meta and value > meta["max"]:
            return False, f"{key} max is {meta['max']}"
    return True, ""


def validate_config_cross(overrides: dict) -> list[str]:
    """Cross-validate config values that depend on each other.
    Returns list of error strings (empty = ok)."""
    errors = []

    def _val(key):
        """Get value from overrides or current setting."""
        if key in overrides:
            return overrides[key]
        return get(key)

    # stop_loss must be < take_profit
    sl = _val("stop_loss_pct")
    tp = _val("take_profit_pct")
    if sl is not None and tp is not None and sl >= tp:
        errors.append(f"stop_loss_pct ({sl}) must be less than take_profit_pct ({tp})")

    # options DTE min must be <= DTE max
    dte_min = _val("options_dte_min")
    dte_max = _val("options_dte_max")
    if dte_min is not None and dte_max is not None and dte_min > dte_max:
        errors.append(f"options_dte_min ({dte_min}) must be <= options_dte_max ({dte_max})")

    # reserve_day_trades must be < day_trade_limit
    reserve = _val("reserve_day_trades")
    limit = _val("day_trade_limit")
    if reserve is not None and limit is not None and reserve >= limit:
        errors.append(f"reserve_day_trades ({reserve}) must be less than day_trade_limit ({limit})")

    # min_score_for_day_trade must be >= min_score_threshold
    dt_score = _val("min_score_for_day_trade")
    min_score = _val("min_score_threshold")
    if dt_score is not None and min_score is not None and dt_score < min_score:
        errors.append(f"min_score_for_day_trade ({dt_score}) must be >= min_score_threshold ({min_score})")

    # stale_position_hours must be <= max_hold_hours
    stale = _val("stale_position_hours")
    max_hold = _val("max_hold_hours")
    if stale is not None and max_hold is not None and stale > max_hold:
        errors.append(f"stale_position_hours ({stale}) must be <= max_hold_hours ({max_hold})")

    return errors
