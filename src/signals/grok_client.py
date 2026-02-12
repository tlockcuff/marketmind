import json
import logging
from typing import List, Optional

from openai import OpenAI

from config import settings
from src.signals.signal_parser import TradeSignal, parse_grok_response, parse_json_signals
from src.signals.usage_tracker import get_tracker

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an analytical swing trading AI focused on multi-day to multi-week setups (2-14 day holds). Your objective is to identify high-conviction trades that capture larger moves over several days, not intraday noise. The account is under $25k (PDT restricted), so day trading is essentially off the table.

When providing trade ideas, always include:
1. Ticker symbol (1-5 letters)
2. Direction: BUY or SELL (SELL = short sell)
3. Confidence level (0-100%) — be measured and analytical; only rate 75+ when the multi-day thesis is strong
4. Entry price suggestion (ideally at support/breakout levels)
5. Stop loss level (wider — 5-8% to accommodate multi-day volatility)
6. Take profit target (15-30% for swing holds)
7. Brief rationale (1-2 sentences focusing on the multi-day catalyst/setup)
8. Overnight/gap risk assessment: low/medium/high with brief explanation

Focus on:
- Breakouts from multi-day/week consolidation patterns
- Trend continuation setups (pullbacks to moving averages in uptrends)
- Earnings catalysts and post-earnings momentum (not same-day reactions)
- Sector rotation and relative strength leaders
- Weekly/monthly chart breakouts at key levels
- Accumulation patterns and institutional buying signals
- Government contracts and federal spending trends
- Trump administration policy impacts (tariffs, deregulation, executive orders)
- Space industry and defense/aerospace developments
- Nuclear energy and uranium plays
- Rare earth materials and critical minerals
- Congressional stock trading activity (STOCK Act filings)
- Weekly and monthly options plays on confirmed setups (7-45 DTE)

Rules:
- Stocks $5+ preferred (need stability for multi-day holds)
- Volume floor: 500k avg daily (liquidity matters for wider stops)
- INCLUDE SHORT opportunities — 3-5 per scan (overextended names, broken trends)
- Be analytical with confidence scores — only rate 75+ when the setup has clear technical + catalyst alignment
- Prioritize "what's setting up this week and next week" over "what's moving right now"
- Assess overnight gap risk for each signal (earnings dates, news catalysts, sector exposure)

For each signal, also assess options suitability:
- options_suitable: true if optionable with decent liquidity (price >$15)
- options_strategy: "directional" for trend plays (7-45 DTE), "spread" for range-bound/mean-reversion, "none" if not suitable
- NO 0DTE plays — minimum 7 DTE for all options

Format response as JSON:
{
  "signals": [
    {
      "ticker": "AAPL",
      "direction": "buy",
      "confidence": 80,
      "entry_price": 185.50,
      "stop_loss": 172.00,
      "take_profit": 215.00,
      "rationale": "Breaking out of 3-week consolidation with rising volume, sector rotation into tech",
      "sector": "Technology",
      "overnight_risk": "low",
      "options_suitable": true,
      "options_strategy": "directional"
    }
  ]
}
"""

SCAN_PROMPT = """Analyze current market conditions and provide 10-15 high-conviction swing trading setups for the coming 1-2 weeks. Focus on QUALITY over quantity.

Prioritize stocks SETTING UP for multi-day moves — breakouts forming, trend continuations, catalyst-driven momentum.

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
- Multi-day consolidation breakouts (tightening ranges, volume drying up before expansion)
- Trend continuation pullbacks (bouncing off 20/50 EMA in uptrends)
- Earnings catalysts in the next 1-2 weeks (pre-earnings run-ups or post-earnings momentum)
- Sector rotation leaders (money flowing into new sectors)
- Weekly chart breakouts at key resistance levels
- Accumulation patterns (higher lows on increasing volume)
- Government contract awards and federal spending
- Trump policy moves (tariffs, deregulation, infrastructure, energy)
- Space industry catalysts (launches, contracts)
- Nuclear/uranium catalysts (reactor approvals, DOE funding)
- Rare earth supply chain developments

INCLUDE 3-5 SHORT SELL OPPORTUNITIES:
- Stocks breaking below major support on weekly chart
- Overextended names with deteriorating fundamentals
- Failed breakouts and distribution patterns
- Sector laggards in weak/rotating-out groups

INCLUDE 3-5 OPTIONS PLAYS:
- Weekly or monthly expiry (7-45 DTE) on confirmed setups
- High-delta calls/puts on breakout confirmations
- NO 0DTE — minimum 7 days to expiration
- Flag these with options_strategy: "directional"

For each signal, assess overnight/gap risk:
- "overnight_risk": "low" / "medium" / "high"
- Consider: upcoming earnings dates, pending FDA/regulatory decisions, geopolitical exposure

Include large caps ($10B+), mid caps ($2-10B), and selective small caps ($500M-2B).
Be analytical with confidence scores — only rate 75+ when technical setup + catalyst align clearly.
Provide specific entry, stop (5-8%), and target (15-30%) levels.

For each signal, include "options_suitable" (true/false) and "options_strategy" ("directional", "spread", or "none")."""

PORTFOLIO_REVIEW_PROMPT = """Review my current swing trading portfolio and provide recommendations. These are multi-day holds (2-14 days).

CURRENT HOLDINGS:
{holdings}

For EACH position, provide one of these actions:
- HOLD: Keep position, thesis intact for multi-day move
- ADD: Add to position on pullback (give new entry level)
- TRIM: Reduce position size (suggest % to trim — e.g., take partial profits)
- EXIT: Close entire position (thesis broken, support lost, or target reached)
- ADJUST_STOPS: Move stop loss (give new level — consider multi-day volatility, use 5-8% stops)

Consider for each position:
- Is the original swing thesis still intact?
- Has the stock reached a resistance level where trimming makes sense?
- Are there upcoming catalysts (earnings, FDA, etc.) that change the risk profile?
- Should stops be tightened to lock in profits or widened to avoid shakeouts?

Also identify 5-8 NEW swing setups that complement the portfolio (avoid correlated positions, diversify sectors).

Format response as JSON:
{{
  "portfolio_actions": [
    {{
      "ticker": "AAPL",
      "action": "hold|add|trim|exit|adjust_stops",
      "confidence": 75,
      "rationale": "Brief reason",
      "new_stop": 172.00,
      "new_target": 215.00
    }}
  ],
  "new_signals": [
    {{
      "ticker": "NVDA",
      "direction": "buy",
      "confidence": 80,
      "entry_price": 130.00,
      "stop_loss": 121.00,
      "take_profit": 160.00,
      "rationale": "Breaking out of 2-week base with sector tailwinds"
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
                temperature=0.4,
                max_tokens=6000,
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
                temperature=0.3,
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
