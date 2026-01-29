import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pytz

from config import settings
from src.analysis.indicators import IndicatorResult, get_technical_alignment_score
from src.analysis.backtester import BacktestResult

logger = logging.getLogger(__name__)


@dataclass
class TradeScore:
    total_score: float
    grok_score: float
    technical_score: float
    backtest_score: float
    volume_score: float
    risk_reward_score: float
    action: str  # strong_buy, buy, hold, weak, avoid
    details: dict


def calculate_trade_score(
    grok_confidence: float,  # 0-100 from Grok
    indicators: Optional[IndicatorResult],
    backtest: Optional[BacktestResult],
    direction: str,
    current_volume: float = None,
    avg_volume: float = None,
    entry_price: float = None,
    stop_loss: float = None,
    take_profit: float = None,
) -> TradeScore:
    """
    Calculate weighted trade score.

    Weights:
    - Grok confidence: 20%
    - Technical alignment: 30%
    - Backtest performance: 20%
    - Volume/momentum: 15%
    - Risk/reward ratio: 15%
    """
    weights = settings.SCORING_WEIGHTS

    # Grok confidence score (already 0-100)
    grok_score = grok_confidence

    # Technical alignment score
    if indicators:
        technical_score = get_technical_alignment_score(indicators, direction)
    else:
        technical_score = 50  # neutral if no data

    # Backtest score
    if backtest:
        backtest_score = backtest.score
    else:
        backtest_score = 50  # neutral if no data

    # Volume/momentum score
    volume_score = calculate_volume_score(current_volume, avg_volume)

    # Risk/reward score
    risk_reward_score = calculate_risk_reward_score(
        entry_price, stop_loss, take_profit, direction
    )

    # Weighted total
    total = (
        grok_score * weights["grok_confidence"]
        + technical_score * weights["technical_alignment"]
        + backtest_score * weights["backtest_performance"]
        + volume_score * weights["volume_momentum"]
        + risk_reward_score * weights["risk_reward"]
    )

    # Determine action
    if total >= 80:
        action = "strong_buy"
    elif total >= 60:
        action = "buy"
    elif total >= 40:
        action = "hold"
    elif total >= 20:
        action = "weak"
    else:
        action = "avoid"

    logger.info(
        f"Score: {total:.1f} ({action}) — grok={grok_score:.0f} tech={technical_score:.0f} "
        f"bt={backtest_score:.0f} vol={volume_score:.0f} rr={risk_reward_score:.0f}"
    )
    return TradeScore(
        total_score=round(total, 2),
        grok_score=round(grok_score, 2),
        technical_score=round(technical_score, 2),
        backtest_score=round(backtest_score, 2),
        volume_score=round(volume_score, 2),
        risk_reward_score=round(risk_reward_score, 2),
        action=action,
        details={
            "indicators": indicators.__dict__ if indicators else None,
            "backtest": backtest.__dict__ if backtest else None,
        },
    )


def calculate_volume_score(
    current_volume: float = None,
    avg_volume: float = None,
) -> float:
    """Score based on volume relative to average, normalized by time of day.

    current_volume is cumulative intraday volume, avg_volume is full-day average.
    We scale avg_volume by fraction of trading day elapsed so the comparison is fair.
    """
    if not current_volume or not avg_volume or avg_volume == 0:
        return 50  # neutral

    # Normalize: scale expected volume by elapsed fraction of trading day
    now_et = datetime.now(pytz.timezone("US/Eastern"))
    market_open_minutes = now_et.hour * 60 + now_et.minute - 570  # 9:30 = 570 min
    market_open_minutes = max(1, min(market_open_minutes, 390))  # clamp 1-390
    day_fraction = market_open_minutes / 390.0
    expected_volume = avg_volume * day_fraction

    ratio = current_volume / expected_volume

    if ratio >= 2.0:
        return 100  # very high volume
    elif ratio >= 1.5:
        return 80
    elif ratio >= 1.0:
        return 60
    elif ratio >= 0.7:
        return 40
    elif ratio >= 0.5:
        return 25
    else:
        return 10  # very low volume


def calculate_risk_reward_score(
    entry_price: float = None,
    stop_loss: float = None,
    take_profit: float = None,
    direction: str = "buy",
) -> float:
    """Score based on risk/reward ratio."""
    if not entry_price or not stop_loss or not take_profit:
        # Use default settings
        stop_loss_pct = settings.STOP_LOSS_PCT
        take_profit_pct = settings.TAKE_PROFIT_PCT
        rr_ratio = take_profit_pct / stop_loss_pct if stop_loss_pct > 0 else 1
    else:
        if direction in ("buy", "long"):
            risk = entry_price - stop_loss
            reward = take_profit - entry_price
        else:
            risk = stop_loss - entry_price
            reward = entry_price - take_profit

        if risk <= 0:
            return 50
        rr_ratio = reward / risk

    # Score based on R:R ratio
    if rr_ratio >= 3:
        return 100
    elif rr_ratio >= 2.5:
        return 85
    elif rr_ratio >= 2:
        return 70
    elif rr_ratio >= 1.5:
        return 55
    elif rr_ratio >= 1:
        return 40
    else:
        return 20


def get_position_size_multiplier(score: float) -> float:
    """
    Return position size multiplier based on score.
    Strong signals get full position, weaker get reduced.
    """
    if score >= 85:
        return 1.0
    elif score >= 75:
        return 0.8
    elif score >= 65:
        return 0.5
    else:
        return 0.0  # don't trade
