import logging
import pandas as pd
import numpy as np
from ta.trend import MACD, SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice, OnBalanceVolumeIndicator
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class IndicatorResult:
    rsi: float
    rsi_signal: str  # oversold, neutral, overbought
    macd: float
    macd_signal_line: float
    macd_histogram: float
    macd_trend: str  # bullish, bearish, neutral
    sma_20: float
    sma_50: float
    ema_9: float
    price_vs_sma20: str  # above, below
    price_vs_sma50: str
    bollinger_upper: float
    bollinger_middle: float
    bollinger_lower: float
    bollinger_position: str  # near_upper, middle, near_lower
    vwap: Optional[float]
    atr: float
    obv_trend: str  # rising, falling, flat
    stochastic_k: float
    stochastic_d: float
    stochastic_signal: str


def calculate_indicators(df: pd.DataFrame) -> Optional[IndicatorResult]:
    """Calculate technical indicators from OHLCV data."""
    if df is None or len(df) < 30:
        logger.warning(f"Insufficient data for indicators: {len(df) if df is not None else 0} rows (need 30)")
        return None

    try:
        logger.info(f"Calculating technicals ({len(df)} bars)...")
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df.get("volume", pd.Series([0] * len(df)))

        # RSI
        rsi_ind = RSIIndicator(close, window=14)
        rsi = rsi_ind.rsi().iloc[-1]
        rsi_signal = "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"

        # MACD
        macd_ind = MACD(close)
        macd = macd_ind.macd().iloc[-1]
        macd_signal_line = macd_ind.macd_signal().iloc[-1]
        macd_hist = macd_ind.macd_diff().iloc[-1]
        macd_trend = "bullish" if macd_hist > 0 else "bearish" if macd_hist < 0 else "neutral"

        # Moving Averages
        sma_20 = SMAIndicator(close, window=20).sma_indicator().iloc[-1]
        sma_50_series = SMAIndicator(close, window=min(50, len(close))).sma_indicator()
        sma_50 = sma_50_series.iloc[-1] if not sma_50_series.isna().all() else sma_20
        ema_9 = EMAIndicator(close, window=9).ema_indicator().iloc[-1]
        current_price = close.iloc[-1]
        price_vs_sma20 = "above" if current_price > sma_20 else "below"
        price_vs_sma50 = "above" if current_price > sma_50 else "below"

        # Bollinger Bands
        bb = BollingerBands(close, window=20, window_dev=2)
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_middle = bb.bollinger_mavg().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_pct = (current_price - bb_lower) / bb_range
            bb_position = "near_upper" if bb_pct > 0.8 else "near_lower" if bb_pct < 0.2 else "middle"
        else:
            bb_position = "middle"

        # VWAP (only valid for intraday)
        vwap = None
        if "vwap" in df.columns:
            vwap = df["vwap"].iloc[-1]
        elif volume.sum() > 0:
            try:
                vwap_ind = VolumeWeightedAveragePrice(high, low, close, volume)
                vwap = vwap_ind.volume_weighted_average_price().iloc[-1]
            except:
                pass

        # ATR
        atr_ind = AverageTrueRange(high, low, close, window=14)
        atr = atr_ind.average_true_range().iloc[-1]

        # OBV
        obv_ind = OnBalanceVolumeIndicator(close, volume)
        obv = obv_ind.on_balance_volume()
        obv_sma = obv.rolling(10).mean()
        obv_trend = "rising" if obv.iloc[-1] > obv_sma.iloc[-1] else "falling"

        # Stochastic
        stoch = StochasticOscillator(high, low, close)
        stoch_k = stoch.stoch().iloc[-1]
        stoch_d = stoch.stoch_signal().iloc[-1]
        stoch_signal = "oversold" if stoch_k < 20 else "overbought" if stoch_k > 80 else "neutral"

        logger.info(f"Technicals done: RSI={rsi:.0f}({rsi_signal}) MACD={macd_trend} BB={bb_position} OBV={obv_trend}")
        return IndicatorResult(
            rsi=rsi,
            rsi_signal=rsi_signal,
            macd=macd,
            macd_signal_line=macd_signal_line,
            macd_histogram=macd_hist,
            macd_trend=macd_trend,
            sma_20=sma_20,
            sma_50=sma_50,
            ema_9=ema_9,
            price_vs_sma20=price_vs_sma20,
            price_vs_sma50=price_vs_sma50,
            bollinger_upper=bb_upper,
            bollinger_middle=bb_middle,
            bollinger_lower=bb_lower,
            bollinger_position=bb_position,
            vwap=vwap,
            atr=atr,
            obv_trend=obv_trend,
            stochastic_k=stoch_k,
            stochastic_d=stoch_d,
            stochastic_signal=stoch_signal,
        )
    except Exception as e:
        logger.error(f"Indicator calculation failed: {e}", exc_info=True)
        return None


def _lerp(value: float, low: float, high: float, out_low: float, out_high: float) -> float:
    """Linear interpolation: map value from [low,high] to [out_low,out_high], clamped."""
    if high == low:
        return (out_low + out_high) / 2
    t = max(0.0, min(1.0, (value - low) / (high - low)))
    return out_low + t * (out_high - out_low)


def mtf_alignment_score(
    mtf_data: dict[str, Optional[pd.DataFrame]],
    direction: str,
) -> float:
    """Calculate multi-timeframe alignment score.

    Args:
        mtf_data: Dict mapping timeframe (e.g. "1h", "4h", "1d") to DataFrame
        direction: "buy"/"long" or "sell"/"short"

    Returns:
        Score 0-100. 100 = all timeframes aligned with direction, 0 = all opposite
    """
    if not mtf_data:
        return 50  # neutral if no data

    is_buy = direction in ("buy", "long")
    trends = []

    for tf, df in mtf_data.items():
        if df is None or len(df) < 20:
            continue

        try:
            close = df["close"]
            # Determine trend: SMA20 vs SMA50
            sma_20 = SMAIndicator(close, window=20).sma_indicator().iloc[-1]
            sma_50_series = SMAIndicator(close, window=min(50, len(close))).sma_indicator()
            sma_50 = sma_50_series.iloc[-1] if not sma_50_series.isna().all() else sma_20
            current_price = close.iloc[-1]

            # Trend determination
            if sma_20 > sma_50 * 1.01 and current_price > sma_20:
                trends.append("bullish")
            elif sma_20 < sma_50 * 0.99 and current_price < sma_20:
                trends.append("bearish")
            else:
                trends.append("neutral")

            logger.debug(f"MTF {tf}: trend={trends[-1]} (price={current_price:.2f}, SMA20={sma_20:.2f}, SMA50={sma_50:.2f})")
        except Exception as e:
            logger.warning(f"MTF trend calc failed for {tf}: {e}")
            continue

    if not trends:
        return 50  # neutral if no valid data

    # Count alignment
    aligned_count = sum(1 for t in trends if (is_buy and t == "bullish") or (not is_buy and t == "bearish"))
    neutral_count = sum(1 for t in trends if t == "neutral")
    opposite_count = sum(1 for t in trends if (is_buy and t == "bearish") or (not is_buy and t == "bullish"))

    total = len(trends)
    alignment_pct = aligned_count / total
    neutral_pct = neutral_count / total
    opposite_pct = opposite_count / total

    # Score: 100 for full alignment, 50 for neutral, 0 for opposite
    score = 50 + (alignment_pct * 50) - (opposite_pct * 50)

    logger.info(f"MTF alignment: {aligned_count}/{total} aligned, {neutral_count} neutral, {opposite_count} opposite → score={score:.1f}")
    return max(0, min(100, score))


def get_technical_alignment_score(indicators: IndicatorResult, direction: str) -> float:
    """Score 0-100 how well technicals align with trade direction. Uses gradient scoring."""
    if direction not in ("buy", "long"):
        direction = "sell"

    score = 50  # neutral start
    is_buy = direction in ("buy", "long")

    # RSI gradient: deeper oversold/overbought = stronger signal
    rsi = indicators.rsi
    if is_buy:
        if rsi < 30:
            score += _lerp(rsi, 0, 30, 15, 5)  # RSI 0->+15, RSI 30->+5
        elif rsi > 70:
            score -= _lerp(rsi, 70, 100, 5, 15)  # RSI 70->-5, RSI 100->-15
    else:
        if rsi > 70:
            score += _lerp(rsi, 70, 100, 5, 15)
        elif rsi < 30:
            score -= _lerp(rsi, 0, 30, 15, 5)

    # MACD gradient: scale by histogram magnitude
    macd_hist = indicators.macd_histogram
    # Normalize histogram relative to price (use macd_signal_line as proxy scale)
    macd_scale = abs(indicators.macd_signal_line) if indicators.macd_signal_line != 0 else 1
    macd_strength = min(abs(macd_hist) / macd_scale, 1.0) if macd_scale else 0
    macd_points = 5 + macd_strength * 10  # 5 to 15 points
    if is_buy:
        score += macd_points if macd_hist > 0 else -macd_points * 0.67
    else:
        score += macd_points if macd_hist < 0 else -macd_points * 0.67

    # Price vs SMAs (unchanged - already binary by nature)
    if is_buy:
        if indicators.price_vs_sma20 == "above":
            score += 5
        if indicators.price_vs_sma50 == "above":
            score += 5
    else:
        if indicators.price_vs_sma20 == "below":
            score += 5
        if indicators.price_vs_sma50 == "below":
            score += 5

    # Bollinger gradient: continuous %B
    bb_range = indicators.bollinger_upper - indicators.bollinger_lower
    if bb_range > 0:
        pct_b = (indicators.bollinger_middle - indicators.bollinger_lower) / bb_range
        # Recalculate with actual price position (using stored values)
        # For buy: lower %B = more bullish (oversold bounce)
        if is_buy:
            score += _lerp(pct_b, 0, 1, 12, -6)  # near lower band = +12, near upper = -6
        else:
            score += _lerp(pct_b, 0, 1, -6, 12)  # near upper = +12 for shorts

    # OBV (unchanged - categorical)
    if is_buy:
        if indicators.obv_trend == "rising":
            score += 10
    else:
        if indicators.obv_trend == "falling":
            score += 10

    # Stochastic gradient
    stoch_k = indicators.stochastic_k
    if is_buy:
        if stoch_k < 20:
            score += _lerp(stoch_k, 0, 20, 12, 5)
        elif stoch_k > 80:
            score -= _lerp(stoch_k, 80, 100, 3, 8)
    else:
        if stoch_k > 80:
            score += _lerp(stoch_k, 80, 100, 5, 12)
        elif stoch_k < 20:
            score -= _lerp(stoch_k, 0, 20, 8, 3)

    return max(0, min(100, score))
