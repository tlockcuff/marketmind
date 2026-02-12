"""Independent momentum screener using Alpaca data.

Scans for gap plays, volume leaders, and unusual activity
without relying on Grok. Feeds signals into the main pipeline.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import (
    StockSnapshotRequest,
    StockBarsRequest,
    MostActivesRequest,
)
from alpaca.data.timeframe import TimeFrame

from config import settings
from src.signals.signal_parser import TradeSignal

logger = logging.getLogger(__name__)


@dataclass
class MomentumSignal:
    ticker: str
    gap_pct: float
    volume_ratio: float  # today vol / avg vol
    direction: str  # "buy" or "sell"
    reason: str


class MomentumScreener:
    def __init__(self):
        self.client = None
        if settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY:
            self.client = StockHistoricalDataClient(
                settings.ALPACA_API_KEY,
                settings.ALPACA_SECRET_KEY,
            )

    def scan(self) -> List[TradeSignal]:
        """Run momentum scan. Returns TradeSignals ready for evaluation."""
        if not self.client:
            return []

        signals = []
        try:
            # Get most active stocks
            actives = self._get_most_actives()
            # Get gap plays from snapshots
            gap_signals = self._scan_gaps(actives)
            signals.extend(gap_signals)
        except Exception as e:
            logger.warning(f"Momentum scan failed: {e}")

        logger.info(f"Momentum screener found {len(signals)} signals")
        return signals

    def _get_most_actives(self) -> List[str]:
        """Get most active tickers from Alpaca."""
        try:
            request = MostActivesRequest(top=50)
            response = self.client.get_most_actives(request)
            tickers = []
            for item in (response.most_actives or []):
                symbol = getattr(item, "symbol", None)
                if symbol:
                    tickers.append(symbol)
            return tickers[:50]
        except Exception as e:
            logger.warning(f"Most actives fetch failed: {e}")
            # Fallback: scan known liquid tickers
            return []

    def _scan_gaps(self, tickers: List[str]) -> List[TradeSignal]:
        """Scan for gap plays: stocks with >3% pre-market gap."""
        if not tickers:
            return []

        signals = []
        try:
            request = StockSnapshotRequest(symbol_or_symbols=tickers[:50])
            snapshots = self.client.get_stock_snapshot(request)
        except Exception as e:
            logger.warning(f"Snapshot fetch failed: {e}")
            return []

        for symbol, snap in (snapshots or {}).items():
            try:
                if not snap or not snap.daily_bar or not snap.previous_daily_bar:
                    continue

                current = snap.daily_bar.close or snap.daily_bar.open
                prev_close = snap.previous_daily_bar.close
                if not current or not prev_close or prev_close <= 0:
                    continue

                gap_pct = (current - prev_close) / prev_close

                # Volume ratio
                today_vol = snap.daily_bar.volume or 0
                # Use minute bar volume as proxy if available
                if snap.minute_bar and snap.minute_bar.volume:
                    today_vol = max(today_vol, snap.minute_bar.volume * 390)

                # Volume ratio filter: require 1.5x previous day's volume
                prev_vol = snap.previous_daily_bar.volume
                if not prev_vol or prev_vol <= 0 or not today_vol or today_vol <= 0:
                    continue
                volume_ratio = today_vol / prev_vol
                if volume_ratio < 1.5:
                    logger.debug(f"{symbol}: low volume ratio {volume_ratio:.1f}x, skipping gap")
                    continue

                # Only trade significant gaps
                if abs(gap_pct) < 0.05:
                    continue

                # Spread check: skip wide-spread stocks (>0.5% of price)
                if snap.latest_quote:
                    bid = getattr(snap.latest_quote, 'bid_price', None) or getattr(snap.latest_quote, 'bp', None)
                    ask = getattr(snap.latest_quote, 'ask_price', None) or getattr(snap.latest_quote, 'ap', None)
                    if bid and ask and bid > 0:
                        spread_pct = (ask - bid) / current
                        if spread_pct > 0.005:
                            logger.debug(f"{symbol}: wide spread {spread_pct:.2%}, skipping")
                            continue

                # Skip penny stocks
                if current < 3:
                    continue

                direction = "buy" if gap_pct > 0 else "sell"
                confidence = min(90, 50 + abs(gap_pct) * 200)  # scale by gap size (less aggressive start)

                # Entry/stop/target (wider for swing trading)
                if direction == "buy":
                    entry = current
                    stop = current * 0.95   # 5% stop
                    target = current * 1.15  # 15% target
                else:
                    entry = current
                    stop = current * 1.05   # 5% stop
                    target = current * 0.88  # 12% target

                signal = TradeSignal(
                    ticker=symbol,
                    direction=direction,
                    confidence=confidence,
                    entry_price=entry,
                    stop_loss=stop,
                    take_profit=target,
                    rationale=f"Momentum screener (potential swing entry): {gap_pct:+.1%} gap, vol={today_vol:,}",
                    sector=None,
                    options_suitable=current > 15,
                    options_strategy="directional" if abs(gap_pct) > 0.05 else "none",
                    signal_source="momentum",
                )
                signals.append(signal)

            except Exception as e:
                logger.debug(f"Error scanning {symbol}: {e}")
                continue

        # Sort by gap magnitude
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals[:15]  # top 15 momentum signals
