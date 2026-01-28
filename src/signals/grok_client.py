import json
import logging
from typing import List, Optional

from openai import OpenAI

from config import settings
from src.signals.signal_parser import TradeSignal, parse_grok_response, parse_json_signals
from src.signals.usage_tracker import get_tracker

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert day trader AI assistant. Your job is to identify high-probability intraday trading opportunities in US equities.

When providing trade ideas, always include:
1. Ticker symbol (1-5 letters)
2. Direction: BUY or SELL
3. Confidence level (0-100%)
4. Entry price suggestion
5. Stop loss level
6. Take profit target
7. Brief rationale (1-2 sentences)

Focus on:
- Momentum plays
- Technical breakouts/breakdowns
- Volume surges
- Earnings/news catalysts
- Sector rotation
- Government contracts and federal spending trends
- Trump administration policy impacts (tariffs, deregulation, executive orders)
- Space industry and defense/aerospace developments
- Nuclear energy and uranium plays
- Rare earth materials and critical minerals
- Congressional stock trading activity: Recent buy/sell disclosures from US Senators and Representatives (STOCK Act filings). These are delayed up to 45 days — treat as directional sentiment, not timing signals. Multiple members buying the same stock is stronger. Note which politician(s) influenced your recommendation in the rationale field.

Avoid:
- Penny stocks under $5
- Low volume stocks (< 500k avg daily volume)
- Highly speculative or risky plays

For each signal, also assess options suitability:
- options_suitable: true if the stock is optionable with good liquidity (>500k avg volume, price >$20)
- options_strategy: "directional" for high-conviction momentum plays, "spread" for range-bound or mean-reversion setups, "none" if options not recommended

Format your response as JSON when possible:
{
  "signals": [
    {
      "ticker": "AAPL",
      "direction": "buy",
      "confidence": 75,
      "entry_price": 185.50,
      "stop_loss": 183.00,
      "take_profit": 190.00,
      "rationale": "Breaking out of consolidation with strong volume",
      "sector": "Technology",
      "options_suitable": true,
      "options_strategy": "directional"
    }
  ]
}
"""

SCAN_PROMPT = """Analyze current market conditions and provide 15-20 day trading opportunities for today.

Scan across ALL sectors:
- Technology (semiconductors, software, cloud)
- Healthcare/Biotech
- Financials (banks, fintech)
- Energy (oil, solar, EVs)
- Consumer (retail, travel, entertainment)
- Industrials (aerospace, defense, manufacturing)
- Space & Defense (launch providers, satellite, defense contractors)
- Nuclear & Uranium (reactors, fuel, SMRs)
- Rare Earth & Critical Minerals (lithium, cobalt, rare earths)

Look for:
- Pre-market movers and gappers (>2% move)
- Unusual volume spikes (>1.5x average)
- Technical breakouts/breakdowns at key levels
- Earnings reactions (today or recent)
- News catalysts (FDA, contracts, guidance)
- Sector rotation plays
- Government contract awards and federal spending announcements
- Trump policy moves (tariffs, deregulation, infrastructure, energy)
- Space industry catalysts (launches, contracts, SPAC activity)
- Nuclear/uranium catalysts (reactor approvals, DOE funding, utility deals)
- Rare earth supply chain news (export restrictions, new mines, stockpiling)

Include a mix of large caps ($10B+), mid caps ($2-10B), and some small caps ($500M-2B).
Provide actionable signals with specific entry, stop, and target levels.

For each signal, include "options_suitable" (true/false) and "options_strategy" ("directional", "spread", or "none").
Flag as options-suitable if: high conviction, optionable stock (price >$20), sufficient options volume."""

PORTFOLIO_REVIEW_PROMPT = """Review my current portfolio and provide recommendations.

CURRENT HOLDINGS:
{holdings}

For EACH position, provide one of these actions:
- HOLD: Keep position, no changes
- ADD: Add to position (give new entry level)
- TRIM: Reduce position size (suggest % to trim)
- EXIT: Close entire position immediately
- ADJUST_STOPS: Move stop loss (give new level)

Also identify 5-10 NEW opportunities that complement the portfolio (avoid correlated positions).

Format response as JSON:
{{
  "portfolio_actions": [
    {{
      "ticker": "AAPL",
      "action": "hold|add|trim|exit|adjust_stops",
      "confidence": 75,
      "rationale": "Brief reason",
      "new_stop": 180.00,
      "new_target": 195.00
    }}
  ],
  "new_signals": [
    {{
      "ticker": "NVDA",
      "direction": "buy",
      "confidence": 80,
      "entry_price": 130.00,
      "stop_loss": 126.00,
      "take_profit": 140.00,
      "rationale": "Momentum breakout"
    }}
  ]
}}"""


class GrokClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.GROK_API_KEY,
            base_url=settings.GROK_BASE_URL,
        )
        self.model = "grok-4-1-fast-reasoning"

    def get_trade_ideas(self, custom_prompt: str = None, market_context: str = None) -> List[TradeSignal]:
        """Query Grok for trade ideas."""
        try:
            prompt = custom_prompt or SCAN_PROMPT
            if market_context:
                prompt = market_context + "\n\n" + prompt

            logger.info("Requesting trade ideas from Grok...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )

            content = response.choices[0].message.content
            logger.info(f"Grok response received ({len(content)} chars)")

            # Track usage
            usage = response.usage
            logger.info("Parsing Grok response...")
            signals = self._try_parse_json(content) or parse_grok_response(content)
            logger.info(f"Parsed {len(signals)} signals from Grok")

            get_tracker().record_request(
                model=self.model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                signals_count=len(signals),
            )

            return signals

        except Exception as e:
            logger.error(f"Grok API error: {e}")
            return []

    def analyze_ticker(self, ticker: str) -> Optional[TradeSignal]:
        """Get Grok's analysis on a specific ticker."""
        try:
            prompt = f"""Analyze {ticker} for a potential day trade today.

Consider:
- Current price action and trend
- Key support/resistance levels
- Volume profile
- Any relevant news or catalysts
- Technical indicator signals

Provide a specific trade recommendation with entry, stop loss, and target."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            content = response.choices[0].message.content
            usage = response.usage
            signals = self._try_parse_json(content) or parse_grok_response(content)

            get_tracker().record_request(
                model=self.model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                signals_count=len(signals),
            )

            # Filter for requested ticker
            for s in signals:
                if s.ticker == ticker.upper():
                    return s
            return signals[0] if signals else None

        except Exception as e:
            logger.error(f"Grok analyze error for {ticker}: {e}")
            return None

    def validate_signal(self, signal: TradeSignal, market_data: dict) -> dict:
        """Ask Grok to validate a signal with current market data."""
        try:
            prompt = f"""Validate this trade signal with current market data:

Signal:
- Ticker: {signal.ticker}
- Direction: {signal.direction}
- Entry: {signal.entry_price}
- Stop: {signal.stop_loss}
- Target: {signal.take_profit}
- Original rationale: {signal.rationale}

Current market data:
- Price: {market_data.get('price')}
- Volume: {market_data.get('volume')}
- Avg Volume: {market_data.get('avg_volume')}
- Day range: {market_data.get('day_low')} - {market_data.get('day_high')}

Is this trade still valid? Provide updated confidence (0-100) and any adjustments to entry/stop/target."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=500,
            )

            return {"response": response.choices[0].message.content}

        except Exception as e:
            logger.error(f"Grok validation error: {e}")
            return {"error": str(e)}

    def get_portfolio_advice(self, holdings: list) -> dict:
        """Get Grok's advice on current portfolio plus new opportunities."""
        try:
            # Format holdings for prompt
            holdings_text = ""
            for h in holdings:
                pl_pct = ((h["current_price"] - h["entry_price"]) / h["entry_price"]) * 100
                pl_sign = "+" if pl_pct >= 0 else ""
                holdings_text += (
                    f"- {h['symbol']}: {h['qty']} shares @ ${h['entry_price']:.2f} "
                    f"(now ${h['current_price']:.2f}, {pl_sign}{pl_pct:.1f}%) "
                    f"SL=${h['stop_loss']:.2f} TP=${h['take_profit']:.2f}\n"
                )

            if not holdings_text:
                holdings_text = "No current positions."

            prompt = PORTFOLIO_REVIEW_PROMPT.format(holdings=holdings_text)

            logger.info(f"Requesting portfolio review from Grok ({len(holdings)} holdings)...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )

            content = response.choices[0].message.content
            logger.info(f"Grok portfolio review received ({len(content)} chars)")

            # Track usage
            usage = response.usage
            get_tracker().record_request(
                model=self.model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                signals_count=0,
            )

            # Parse response
            result = {"portfolio_actions": [], "new_signals": []}
            try:
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    data = json.loads(json_match.group())
                    result["portfolio_actions"] = data.get("portfolio_actions", [])
                    result["new_signals"] = parse_json_signals(
                        data.get("new_signals", [])
                    )
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to parse portfolio advice JSON: {e}")

            return result

        except Exception as e:
            logger.error(f"Grok portfolio review error: {e}")
            return {"portfolio_actions": [], "new_signals": []}

    def _try_parse_json(self, content: str) -> List[TradeSignal]:
        """Try to extract and parse JSON from response."""
        try:
            # Try direct JSON parse
            data = json.loads(content)
            return parse_json_signals(data)
        except json.JSONDecodeError:
            pass

        # Try to find JSON block in response
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return parse_json_signals(data)
            except json.JSONDecodeError:
                pass

        # Try array format
        json_match = re.search(r'\[[\s\S]*\]', content)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return parse_json_signals(data)
            except json.JSONDecodeError:
                pass

        return []
