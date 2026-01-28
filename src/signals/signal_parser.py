import re
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    ticker: str
    direction: str  # buy, sell, short
    confidence: float  # 0-100
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    rationale: str
    timeframe: str  # intraday, swing, etc.
    options_suitable: bool = False
    options_strategy: str = "none"  # "directional", "spread", "none"
    sector: Optional[str] = None


def parse_grok_response(response_text: str) -> List[TradeSignal]:
    """Parse Grok's response into structured trade signals."""
    signals = []

    # Try to extract structured signals
    # Grok should return JSON-like format, but handle free-form too

    # Pattern for ticker mentions (1-5 uppercase letters)
    ticker_pattern = r'\b([A-Z]{1,5})\b'

    # Pattern for direction
    buy_patterns = r'\b(buy|long|bullish|calls?)\b'
    sell_patterns = r'\b(sell|short|bearish|puts?)\b'

    # Pattern for prices
    price_pattern = r'\$?([\d,]+\.?\d*)'

    # Pattern for confidence/probability
    confidence_pattern = r'(\d{1,3})%?\s*(?:confidence|probability|chance|likely)'

    lines = response_text.split('\n')
    current_signal = None

    for line in lines:
        line_lower = line.lower()

        # Find tickers
        tickers = re.findall(ticker_pattern, line)
        # Filter out common words
        tickers = [t for t in tickers if t not in (
            'I', 'A', 'THE', 'AND', 'OR', 'FOR', 'TO', 'IN', 'ON', 'AT',
            'IS', 'IT', 'AS', 'BE', 'BY', 'IF', 'OF', 'US', 'AN', 'UP',
            'SO', 'NO', 'AM', 'PM', 'ET', 'PT', 'USD', 'CEO', 'IPO', 'ETF',
            'AI', 'EV', 'PE', 'RSI', 'MACD', 'SMA', 'EMA', 'ATR', 'VWAP',
        )]

        if not tickers:
            continue

        # Determine direction
        is_buy = bool(re.search(buy_patterns, line_lower))
        is_sell = bool(re.search(sell_patterns, line_lower))

        if not is_buy and not is_sell:
            continue

        direction = "buy" if is_buy else "sell"

        # Extract confidence
        conf_match = re.search(confidence_pattern, line_lower)
        confidence = float(conf_match.group(1)) if conf_match else 70  # default

        # Extract prices
        prices = re.findall(price_pattern, line)
        prices = [float(p.replace(',', '')) for p in prices if float(p.replace(',', '')) > 0]

        entry_price = None
        stop_loss = None
        take_profit = None

        if prices:
            if 'entry' in line_lower or 'at' in line_lower:
                entry_price = prices[0]
            if 'stop' in line_lower and len(prices) > 0:
                stop_loss = prices[-1] if len(prices) == 1 else prices[1] if len(prices) > 1 else None
            if 'target' in line_lower or 'profit' in line_lower:
                take_profit = prices[-1]

        # Extract rationale (rest of line after ticker)
        rationale = line

        # Determine timeframe
        timeframe = "intraday"
        if any(w in line_lower for w in ['swing', 'days', 'week']):
            timeframe = "swing"
        elif any(w in line_lower for w in ['scalp', 'minute', 'quick']):
            timeframe = "scalp"

        for ticker in tickers:
            signal = TradeSignal(
                ticker=ticker,
                direction=direction,
                confidence=min(100, max(0, confidence)),
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                rationale=rationale,
                timeframe=timeframe,
            )
            signals.append(signal)
            logger.info(f"Parsed signal: {ticker} {direction} conf={confidence}")

    return signals


def parse_json_signals(json_data: dict) -> List[TradeSignal]:
    """Parse JSON-formatted signals from Grok."""
    signals = []

    if isinstance(json_data, dict):
        if 'signals' in json_data:
            items = json_data['signals']
        elif 'trades' in json_data:
            items = json_data['trades']
        else:
            items = [json_data]
    elif isinstance(json_data, list):
        items = json_data
    else:
        return signals

    for item in items:
        if not isinstance(item, dict):
            continue

        ticker = item.get('ticker') or item.get('symbol')
        if not ticker:
            continue

        signal = TradeSignal(
            ticker=ticker.upper(),
            direction=item.get('direction', item.get('action', 'buy')).lower(),
            confidence=float(item.get('confidence', item.get('probability', 70))),
            entry_price=item.get('entry_price') or item.get('entry'),
            stop_loss=item.get('stop_loss') or item.get('stop'),
            take_profit=item.get('take_profit') or item.get('target'),
            rationale=item.get('rationale', item.get('reason', '')),
            timeframe=item.get('timeframe', 'intraday'),
            options_suitable=bool(item.get('options_suitable', False)),
            options_strategy=item.get('options_strategy', 'none'),
            sector=item.get('sector'),
        )
        signals.append(signal)

    return signals
