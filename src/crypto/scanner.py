"""Crypto-specific signal generation: technical + Grok-based scanning."""

import logging
from typing import List, Optional

import pandas as pd
from alpaca.data import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import timedelta

from config import settings
from src.utils import utcnow
from src.analysis.indicators import calculate_indicators, IndicatorResult
from src.signals.grok_client import GrokClient
from src.signals.signal_parser import TradeSignal
from src.crypto.config import CRYPTO_SYMBOLS, CRYPTO_MIN_SCORE_THRESHOLD

logger = logging.getLogger(__name__)


class CryptoScanner:
    """Generates crypto trade signals from technical analysis and Grok AI."""

    def __init__(self, grok: GrokClient):
        self.grok = grok
        self.crypto_client = CryptoHistoricalDataClient()  # no keys needed for crypto market data

    # ------------------------------------------------------------------
    # Market data helpers
    # ------------------------------------------------------------------

    def get_crypto_bars(self, symbol: str, days: int = 60, timeframe: str = "1d") -> Optional[pd.DataFrame]:
        """Fetch crypto bars from Alpaca crypto data API."""
        try:
            tf_map = {
                "1m": TimeFrame.Minute,
                "5m": TimeFrame(5, "Min"),
                "15m": TimeFrame(15, "Min"),
                "1h": TimeFrame.Hour,
                "1d": TimeFrame.Day,
            }
            tf = tf_map.get(timeframe, TimeFrame.Day)
            end = utcnow()
            start = end - timedelta(days=days)
            request = CryptoBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start,
                end=end,
            )
            bars = self.crypto_client.get_crypto_bars(request)
            df = bars.df
            if symbol in df.index.get_level_values(0):
                df = df.loc[symbol]
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            if df.empty:
                return None
            return df
        except Exception as e:
            logger.warning(f"Failed to fetch crypto bars for {symbol}: {e}")
            return None

    def get_crypto_price(self, symbol: str) -> Optional[float]:
        """Get latest crypto price from a short bar request."""
        df = self.get_crypto_bars(symbol, days=2, timeframe="1h")
        if df is not None and not df.empty:
            return float(df["close"].iloc[-1])
        return None

    # ------------------------------------------------------------------
    # Technical scanner
    # ------------------------------------------------------------------

    def technical_scan(self, symbols: List[str] = None) -> List[TradeSignal]:
        """Run technical indicators on crypto symbols and generate signals."""
        symbols = symbols or CRYPTO_SYMBOLS
        signals: List[TradeSignal] = []

        for symbol in symbols:
            try:
                df = self.get_crypto_bars(symbol, days=60, timeframe="1d")
                if df is None or len(df) < 30:
                    logger.debug(f"Insufficient data for {symbol}")
                    continue

                indicators = calculate_indicators(df)
                if indicators is None:
                    continue

                price = float(df["close"].iloc[-1])
                vol = float(df["volume"].iloc[-1]) if "volume" in df.columns else 0
                avg_vol = float(df["volume"].rolling(20).mean().iloc[-1]) if "volume" in df.columns else 0
                vol_spike = vol > avg_vol * 1.3 if avg_vol > 0 else False

                signal = self._evaluate_technicals(symbol, price, indicators, vol_spike)
                if signal:
                    signals.append(signal)

            except Exception as e:
                logger.warning(f"Technical scan error for {symbol}: {e}")

        logger.info(f"Crypto technical scan: {len(signals)} signals from {len(symbols)} symbols")
        return signals

    def _evaluate_technicals(
        self,
        symbol: str,
        price: float,
        ind: IndicatorResult,
        vol_spike: bool,
    ) -> Optional[TradeSignal]:
        """Evaluate indicator conditions and return a signal if criteria met."""
        confidence = 0.0
        reasons = []
        direction = "buy"

        # RSI oversold bounce
        if ind.rsi < 30:
            confidence += 25
            reasons.append(f"RSI oversold ({ind.rsi:.0f})")

        # RSI > 70 with bullish momentum (trend continuation)
        if ind.rsi > 70 and ind.macd_histogram > 0 and ind.obv_trend == "rising":
            confidence += 20
            reasons.append(f"RSI momentum continuation ({ind.rsi:.0f})")

        # MACD bullish crossover
        if ind.macd_trend == "bullish" and abs(ind.macd_histogram) > 0:
            prev_bearish = ind.macd_histogram > 0  # histogram just turned positive
            confidence += 15
            reasons.append("MACD bullish crossover")

        # MACD bearish crossover → short signal
        if ind.macd_trend == "bearish" and ind.rsi > 60:
            confidence += 15
            direction = "sell"
            reasons.append("MACD bearish crossover")

        # Bollinger Band breakout with volume
        if ind.bollinger_position == "near_lower" and vol_spike:
            confidence += 20
            reasons.append("BB lower band bounce + volume")
        elif ind.bollinger_position == "near_upper" and vol_spike and ind.macd_trend == "bullish":
            confidence += 15
            reasons.append("BB upper breakout + volume")

        # VWAP cross with volume
        if ind.vwap and price > ind.vwap and vol_spike:
            confidence += 15
            reasons.append("Price above VWAP + volume")
        elif ind.vwap and price < ind.vwap and vol_spike and direction == "sell":
            confidence += 15
            reasons.append("Price below VWAP + volume")

        if confidence < CRYPTO_MIN_SCORE_THRESHOLD:
            return None

        # Cap confidence
        confidence = min(confidence, 95)

        # Compute stop/target from ATR
        atr = ind.atr if ind.atr else price * 0.03
        if direction == "buy":
            stop_loss = round(price - 2 * atr, 2)
            take_profit = round(price + 4 * atr, 2)
        else:
            stop_loss = round(price + 2 * atr, 2)
            take_profit = round(price - 4 * atr, 2)

        return TradeSignal(
            ticker=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rationale="; ".join(reasons),
            timeframe="crypto_swing",
            signal_source="crypto_technical",
        )

    # ------------------------------------------------------------------
    # Grok scanner
    # ------------------------------------------------------------------

    def grok_scan(self) -> List[TradeSignal]:
        """Get crypto trade ideas from Grok AI."""
        return self.grok.get_crypto_ideas()

    # ------------------------------------------------------------------
    # Combined scan
    # ------------------------------------------------------------------

    def scan(self) -> List[TradeSignal]:
        """Run both technical and Grok scans, deduplicate, return merged list."""
        tech_signals = self.technical_scan()
        grok_signals = self.grok_scan()

        # Dedupe: prefer Grok signal if same symbol
        seen = {}
        for s in grok_signals:
            seen[s.ticker] = s
        for s in tech_signals:
            if s.ticker not in seen:
                seen[s.ticker] = s

        merged = list(seen.values())
        logger.info(f"Crypto scan total: {len(merged)} signals (tech={len(tech_signals)}, grok={len(grok_signals)})")
        return merged
