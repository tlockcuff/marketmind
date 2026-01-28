#!/usr/bin/env python3
"""
Autonomous Day Trading Bot
Uses Grok AI for signals, quantitative validation, Alpaca for execution.
"""

import argparse
import atexit
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from config import settings

# PID lock file to prevent multiple instances
LOCK_FILE = Path(__file__).parent.parent / "logs" / "bot.lock"
from config.logging_config import setup_logging
from src.signals.grok_client import GrokClient
from src.analysis.market_data import MarketDataFetcher
from src.analysis.indicators import calculate_indicators
from src.analysis.backtester import backtest_signal
from src.analysis.scorer import calculate_trade_score
from src.trading.alpaca_client import AlpacaClient
from src.trading.position_mgr import PositionManager
from src.trading.risk_mgr import RiskManager
from src.trading.trade_history import get_trade_history
from config.sectors import get_sector
from src.notifications.discord import DiscordNotifier
from src.trading.options.contracts import ContractSelector
from src.trading.options.executor import OptionsExecutor
from src.trading.options.sizing import OptionsSizer
from src.trading.options.position_mgr import OptionsPositionManager
from src.signals.congress_client import CongressClient
from src.scheduler.trading_hours import (
    is_market_open,
    is_trading_day,
    should_avoid_trading,
    format_market_status,
    time_until_open,
)

logger = logging.getLogger(__name__)


def acquire_lock() -> bool:
    """Acquire PID lock. Returns True if successful."""
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            # Check if process is still running
            os.kill(pid, 0)
            logger.error(f"Another bot instance running (PID {pid})")
            return False
        except (ProcessLookupError, ValueError):
            # Stale lock file, remove it
            LOCK_FILE.unlink(missing_ok=True)

    LOCK_FILE.parent.mkdir(exist_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    atexit.register(release_lock)
    return True


def release_lock():
    """Release PID lock."""
    LOCK_FILE.unlink(missing_ok=True)


class TradingBot:
    def __init__(self, paper: bool = True):
        self.paper = paper
        self.grok = GrokClient()
        self.market_data = MarketDataFetcher()
        self.alpaca = AlpacaClient()
        self.position_mgr = PositionManager()
        self.risk_mgr = RiskManager()
        self.discord = DiscordNotifier()
        self.congress = CongressClient() if settings.CONGRESS_ENABLED else None
        self.ticker_blacklist: set = set()  # Tickers that failed data fetch
        self._owned_symbols: set = set()  # Cache of owned symbols for quick lookup
        self._current_regime: str = "choppy"  # Market regime

        # Options components
        self.options_enabled = settings.OPTIONS_ENABLED
        if self.options_enabled:
            trading_client = self.alpaca.client
            self.contract_selector = ContractSelector(trading_client)
            self.options_executor = OptionsExecutor(trading_client)
            self.options_position_mgr = OptionsPositionManager(self.options_executor)
            logger.info("Options trading enabled")

        logger.info(f"Trading bot initialized (paper={paper})")

    def run(self):
        """Main trading loop."""
        logger.info("Starting trading bot...")
        self.discord.alert("Bot Started", format_market_status(), "info")

        # Run a trading cycle immediately on startup
        if is_market_open():
            try:
                can_trade, msg = self.risk_mgr.can_trade()
                if can_trade:
                    self._trading_cycle()
                else:
                    logger.warning(f"Startup cycle skipped: {msg}")
            except Exception as e:
                logger.exception(f"Error in startup cycle: {e}")

        while True:
            try:
                # Wait for market open
                if not is_market_open():
                    if is_trading_day():
                        wait = time_until_open()
                        if wait and wait > 0:
                            logger.info(f"Market closed. Waiting {wait}s until open...")
                            time.sleep(min(wait, 60))
                            continue
                    else:
                        logger.info("Not a trading day. Sleeping 1 hour...")
                        time.sleep(3600)
                        continue

                # Check if we should avoid trading
                avoid, reason = should_avoid_trading()
                if avoid:
                    logger.info(f"Avoiding trading: {reason}")
                    time.sleep(60)
                    continue

                # Check risk limits
                logger.info("Checking risk limits...")
                can_trade, msg = self.risk_mgr.can_trade()
                if not can_trade:
                    logger.warning(f"Trading blocked: {msg}")
                    if "loss limit" in msg.lower():
                        self.discord.daily_loss_limit_hit(
                            settings.DAILY_LOSS_LIMIT_PCT,
                            self.alpaca.get_account().get("equity", 0),
                        )
                    time.sleep(300)
                    continue

                # Run trading cycle
                self._trading_cycle()

                # Sleep until next scan
                logger.info(f"Sleeping {settings.SCAN_INTERVAL_MINUTES} minutes...")
                time.sleep(settings.SCAN_INTERVAL_MINUTES * 60)

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                self._send_daily_summary()
                break
            except Exception as e:
                logger.exception(f"Error in main loop: {e}")
                self.discord.alert("Bot Error", str(e), "error")
                time.sleep(60)

    def _trading_cycle(self):
        """Single trading cycle."""
        logger.info("=== Starting trading cycle ===")

        # 0. Determine market regime
        regime_info = self.market_data.get_market_regime()
        self._current_regime = regime_info.get("regime", "choppy")
        logger.info(f"Market regime: {self._current_regime} (VIX={regime_info.get('vix')})")

        # 1. Get current positions and cache
        positions = self.alpaca.get_positions()
        self._owned_symbols = {p["symbol"] for p in positions}

        # 2. Get portfolio-aware advice from Grok
        if positions:
            self._review_portfolio(positions)

        # 3. Check stop/target exits
        self._check_positions()

        # 3b. Check options exits
        if self.options_enabled:
            self._check_options_positions()

        # 4. Get new signals if we have room (stocks or options)
        can_open_stock = self.position_mgr.can_open_position()
        can_open_options = (self.options_enabled
                           and self.options_position_mgr.can_open())

        if can_open_stock or can_open_options:
            market_context = self.market_data.get_market_context()
            # Append regime to context for Grok
            regime_line = f"\nMarket is {self._current_regime}, VIX={regime_info.get('vix', 'N/A')}"
            if market_context:
                market_context += regime_line
            else:
                market_context = regime_line

            # Append account stats so Grok can calibrate risk
            account = self.alpaca.get_account()
            if account:
                equity = account.get("equity", 0)
                daily_pl = equity - self.risk_mgr.daily_stats.starting_equity
                daily_pct = (daily_pl / self.risk_mgr.daily_stats.starting_equity * 100) if self.risk_mgr.daily_stats.starting_equity else 0
                open_count = len(positions)
                max_pos = settings.MAX_CONCURRENT_POSITIONS
                market_context += (
                    f"\n\nACCOUNT STATUS:"
                    f"\nEquity: ${equity:,.0f} | Daily P/L: ${daily_pl:+,.0f} ({daily_pct:+.1f}%)"
                    f"\nPositions: {open_count}/{max_pos} | Buying power: ${account.get('buying_power', 0):,.0f}"
                )

            if self.congress:
                try:
                    congress_ctx = self.congress.build_context_string()
                    if congress_ctx:
                        market_context += "\n\n" + congress_ctx
                except Exception as e:
                    logger.warning(f"Congress data fetch failed: {e}")

            signals = self.grok.get_trade_ideas(market_context=market_context)
            logger.info(f"Got {len(signals)} signals from Grok")

            for signal in signals:
                # Stop if both stock and options slots are full
                can_open_stock = self.position_mgr.can_open_position()
                can_open_options = (self.options_enabled
                                   and self.options_position_mgr.can_open())
                if not can_open_stock and not can_open_options:
                    logger.info("All position slots full, stopping signal evaluation")
                    break
                self._evaluate_signal(signal)
        else:
            logger.info("All position slots full, skipping new signal scan")

        # 5. Scan for covered call opportunities on existing positions
        if self.options_enabled:
            self._scan_covered_calls()

        logger.info("=== Trading cycle complete ===")

    def _check_positions(self):
        """Check and manage existing positions."""
        positions = self.position_mgr.get_positions_summary()
        if not positions:
            return

        # Get current prices
        current_prices = {}
        for p in positions:
            price = self.market_data.get_current_price(p["symbol"])
            if price:
                current_prices[p["symbol"]] = price

        # Update trailing stops
        for symbol, pos in self.position_mgr.positions.items():
            price = current_prices.get(symbol)
            if not price:
                continue
            new_stop = self.risk_mgr.calculate_trailing_stop(
                entry_price=pos.entry_price,
                current_price=price,
                current_stop=pos.stop_loss,
                direction=pos.direction,
                atr=pos.atr,
            )
            if new_stop != pos.stop_loss:
                logger.info(f"Trailing stop {symbol}: {pos.stop_loss:.2f} -> {new_stop:.2f}")
                self.position_mgr.update_stop_loss(symbol, new_stop)
                pos.trailing_stop_updates += 1

        # Check exits
        closed = self.position_mgr.check_exits(current_prices)
        for symbol in closed:
            logger.info(f"Position closed: {symbol}")

    def _review_portfolio(self, positions: list):
        """Get Grok's advice on current portfolio."""
        # Build holdings data for Grok
        trade_history = get_trade_history()
        holdings = []
        for p in positions:
            trade_info = trade_history.get_trade_info(p["symbol"]) or {}
            holdings.append({
                "symbol": p["symbol"],
                "qty": p["qty"],
                "entry_price": trade_info.get("entry_price", p["avg_entry"]),
                "current_price": p["current_price"],
                "stop_loss": trade_info.get("stop_loss", p["avg_entry"] * 0.97),
                "take_profit": trade_info.get("take_profit", p["avg_entry"] * 1.08),
            })

        logger.info(f"Reviewing {len(holdings)} positions with Grok...")
        advice = self.grok.get_portfolio_advice(holdings)

        # Process portfolio actions
        for action in advice.get("portfolio_actions", []):
            self._process_portfolio_action(action)

    def _process_portfolio_action(self, action: dict):
        """Process a portfolio action from Grok."""
        ticker = action.get("ticker", "").upper()
        action_type = action.get("action", "").lower()
        confidence = action.get("confidence", 0)
        rationale = action.get("rationale", "")

        if not ticker or not action_type:
            return

        # Only act on high confidence recommendations
        if confidence < 70:
            logger.debug(f"{ticker}: {action_type} (low confidence {confidence})")
            return

        # Enforce minimum hold time before Grok can exit
        if action_type == "exit":
            trade_info = get_trade_history().get_trade_info(ticker)
            if trade_info and trade_info.get("opened_at"):
                from datetime import datetime as dt
                opened_at = trade_info["opened_at"]
                if isinstance(opened_at, str):
                    try:
                        opened_at = dt.fromisoformat(opened_at)
                    except (ValueError, TypeError):
                        opened_at = None
                if opened_at:
                    hold_minutes = (datetime.now() - opened_at.replace(tzinfo=None)).total_seconds() / 60
                    if hold_minutes < settings.MIN_HOLD_MINUTES:
                        logger.info(f"{ticker}: skip Grok exit, held only {hold_minutes:.0f}m (min {settings.MIN_HOLD_MINUTES}m)")
                        return

        if action_type == "exit":
            logger.info(f"Grok EXIT signal for {ticker}: {rationale}")
            if self.position_mgr.close_position(ticker, reason="grok_exit"):
                self._owned_symbols.discard(ticker)
                price = self.market_data.get_current_price(ticker)
                if price:
                    get_trade_history().record_close(ticker, price, "grok_exit")
                self.discord.alert("Position Closed", f"{ticker} - {rationale}", "warning")

        elif action_type == "adjust_stops":
            new_stop = action.get("new_stop")
            if new_stop:
                logger.info(f"Grok ADJUST STOP for {ticker}: ${new_stop:.2f}")
                self.position_mgr.update_stop_loss(ticker, new_stop)
                # Note: bracket orders would need API modification

        elif action_type == "hold":
            logger.debug(f"{ticker}: HOLD - {rationale}")

        elif action_type in ("add", "trim"):
            # TODO: implement partial position changes
            logger.info(f"Grok {action_type.upper()} for {ticker}: {rationale} (not implemented)")

    def _evaluate_signal(self, signal):
        """Evaluate and potentially execute a signal."""
        ticker = signal.ticker

        # Skip blacklisted tickers (failed data fetch previously)
        if ticker in self.ticker_blacklist:
            return

        # Handle sell/short signals
        if signal.direction in ("sell", "short"):
            if not settings.ALLOW_SHORT_SELLING:
                # Check if we own this stock
                if ticker not in self._owned_symbols:
                    return  # Silently skip - we don't own it and can't short

                # We own it and Grok says sell - close the position
                logger.info(f"Sell signal for {ticker} - closing position")
                if self.position_mgr.close_position(ticker, reason="grok_sell_signal"):
                    self._owned_symbols.discard(ticker)
                    # Record close in trade history
                    price = self.market_data.get_current_price(ticker)
                    if price:
                        get_trade_history().record_close(ticker, price, "grok_sell_signal")
                    self.discord.alert("Position Closed", f"{ticker} - Grok sell signal", "warning")
                return

        # For buy signals: skip if we already own this stock (check EARLY to save API calls)
        if ticker in self._owned_symbols:
            logger.debug(f"Skip {ticker} - already own")
            return

        logger.info(f"Evaluating signal: {ticker} {signal.direction} (conf={signal.confidence:.0f}%)")

        # Get market data
        logger.info(f"{ticker}: fetching market data...")
        df = self.market_data.get_bars(ticker, days=settings.BACKTEST_DAYS)
        if df is None or df.empty:
            logger.warning(f"No market data for {ticker} - blacklisting")
            self.ticker_blacklist.add(ticker)
            return

        quote = self.market_data.get_quote(ticker)
        current_price = quote.get("price") if quote else None
        if not current_price:
            logger.warning(f"No current price for {ticker} - blacklisting")
            self.ticker_blacklist.add(ticker)
            return

        # Calculate indicators
        logger.info(f"{ticker}: running technical indicators...")
        indicators = calculate_indicators(df)

        # Run backtest
        logger.info(f"{ticker}: running backtest...")
        backtest = backtest_signal(df, signal.direction)

        # Pre-calc stop/target so scorer gets real R:R
        atr = indicators.atr if indicators else None
        stop_loss = self.risk_mgr.calculate_stop_loss(
            current_price, signal.direction, atr
        )
        take_profit = self.risk_mgr.calculate_take_profit(
            current_price, signal.direction, stop_loss
        )

        # Score the trade
        logger.info(f"{ticker}: scoring trade...")
        score = calculate_trade_score(
            grok_confidence=signal.confidence,
            indicators=indicators,
            backtest=backtest,
            direction=signal.direction,
            current_volume=quote.get("volume") if quote else None,
            avg_volume=quote.get("avg_volume") if quote else None,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        logger.info(f"{ticker} score: {score.total_score} ({score.action})")

        # Apply market regime filter
        regime = getattr(self, "_current_regime", "choppy")
        score_threshold = settings.MIN_SCORE_THRESHOLD
        if regime == "high_volatility":
            score_threshold = 75
        elif regime == "trending_down" and signal.direction in ("buy", "long"):
            score_threshold = 70
        # sizing adjustments handled in _execute_trade

        # Resolve sector
        sector = get_sector(ticker, signal.sector)

        # Execute if score meets threshold
        if score.total_score >= score_threshold:
            # Sector concentration check
            can_sector, sector_msg = self.position_mgr.can_open_in_sector(sector)
            if not can_sector:
                logger.info(f"Skipping {ticker}: {sector_msg}")
                get_trade_history().record_rejected(
                    symbol=ticker, direction=signal.direction,
                    score=score.total_score, reason=sector_msg,
                    score_breakdown={"grok": score.grok_score, "technical": score.technical_score,
                                     "backtest": score.backtest_score, "volume": score.volume_score,
                                     "risk_reward": score.risk_reward_score},
                    sector=sector,
                )
                return

            trade_type = self._decide_trade_type(signal, score, current_price, indicators)
            if trade_type == "skip":
                return
            elif trade_type == "spread":
                self._execute_spread_trade(signal, score, current_price)
            elif trade_type == "directional_option":
                self._execute_options_trade(signal, score, current_price, indicators)
            else:
                self._execute_trade(signal, score, current_price, indicators, sector=sector)
        else:
            # Record rejected signal
            get_trade_history().record_rejected(
                symbol=ticker, direction=signal.direction,
                score=score.total_score, reason=f"below_threshold_{score_threshold}",
                score_breakdown={"grok": score.grok_score, "technical": score.technical_score,
                                 "backtest": score.backtest_score, "volume": score.volume_score,
                                 "risk_reward": score.risk_reward_score},
                sector=sector,
            )
            # Notify about signal found but not traded
            self.discord.signal_found(
                ticker,
                signal.direction,
                score.total_score,
                signal.rationale,
            )

    def _execute_trade(self, signal, score, current_price, indicators, sector: str = None):
        """Execute a trade."""
        ticker = signal.ticker

        # Determine trade strategy (day trade vs swing trade)
        trade_strategy = self.risk_mgr.get_trade_strategy(score.total_score)
        can_dt, dt_reason = self.risk_mgr.can_day_trade(score.total_score)

        if not settings.is_paper_mode():
            logger.info(f"{ticker} strategy: {trade_strategy} ({dt_reason})")

        # Calculate position size (volatility-adjusted)
        atr = indicators.atr if indicators else None
        qty = self.position_mgr.get_position_size(current_price, score.total_score, atr=atr)

        # Regime-based sizing adjustment
        regime = getattr(self, "_current_regime", "choppy")
        if regime == "high_volatility":
            qty = max(1, int(qty * 0.5))
        elif regime == "choppy":
            qty = max(1, int(qty * 0.7))

        if qty < 1:
            logger.info(f"Position size too small for {ticker}")
            return

        # Validate with risk manager
        valid, msg, adjusted_qty = self.risk_mgr.validate_position_size(
            ticker, qty, current_price
        )
        if not valid:
            logger.warning(f"Position validation failed: {msg}")
            return
        qty = adjusted_qty

        # Always calculate stop/target from current price (Grok's prices may be stale)
        stop_loss = self.risk_mgr.calculate_stop_loss(
            current_price, signal.direction, atr
        )
        take_profit = self.risk_mgr.calculate_take_profit(
            current_price, signal.direction, stop_loss
        )
        logger.info(f"{ticker} entry={current_price:.2f} SL={stop_loss:.2f} TP={take_profit:.2f}")

        # Open position
        success = self.position_mgr.open_position(
            symbol=ticker,
            qty=qty,
            direction=signal.direction,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            score=score.total_score,
            use_bracket=True,
            atr=atr,
            sector=sector,
        )

        if success:
            # Update owned symbols cache
            self._owned_symbols.add(ticker)

            # Record trade with rationale
            get_trade_history().record_open(
                symbol=ticker,
                direction=signal.direction,
                qty=qty,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                score=score.total_score,
                grok_rationale=signal.rationale or "No rationale provided",
                score_breakdown={
                    "grok": score.grok_score,
                    "technical": score.technical_score,
                    "backtest": score.backtest_score,
                    "volume": score.volume_score,
                    "risk_reward": score.risk_reward_score,
                },
                sector=sector,
                atr_at_entry=atr,
            )

            self.discord.trade_executed(
                ticker,
                signal.direction,
                qty,
                current_price,
                stop_loss,
                take_profit,
                score.total_score,
            )

    def _decide_trade_type(self, signal, score, price, indicators) -> str:
        """Decide whether to trade stock, directional option, or spread."""
        can_stock = self.position_mgr.can_open_position()
        can_options = (self.options_enabled
                       and self.options_position_mgr.can_open()
                       and price > 20)

        if not can_stock and not can_options:
            return "stock"  # will fail at execute, but shouldn't reach here

        # If options slots available and score qualifies
        if can_options:
            # Credit spread for high-score + Grok flagged
            if (score.total_score >= settings.OPTIONS_MIN_SCORE_SPREAD
                    and signal.options_strategy == "spread"):
                logger.info(f"Options: routing {signal.ticker} to spread (score={score.total_score})")
                return "spread"

            # Directional option: when score qualifies, or stock slots full
            if score.total_score >= settings.OPTIONS_MIN_SCORE_DIRECTIONAL:
                logger.info(f"Options: routing {signal.ticker} to directional_option (score={score.total_score})")
                return "directional_option"

            # Stock positions full — try options even at lower scores
            if not can_stock and score.total_score >= settings.MIN_SCORE_THRESHOLD:
                logger.info(f"Options: stock full, routing {signal.ticker} to directional_option (score={score.total_score})")
                return "directional_option"

        if not can_stock:
            logger.debug(f"Skip {signal.ticker}: stock full, options not viable")
            return "skip"

        return "stock"

    def _execute_options_trade(self, signal, score, price, indicators):
        """Execute a directional options trade."""
        ticker = signal.ticker
        logger.info(f"Attempting directional option for {ticker} (score={score.total_score})")
        contract = self.contract_selector.find_directional_contract(
            ticker, signal.direction, price, score.total_score
        )
        if not contract:
            if self.position_mgr.can_open_position():
                logger.info(f"No liquid option for {ticker}, falling back to stock")
                self._execute_trade(signal, score, price, indicators)
            else:
                logger.info(f"No liquid option for {ticker}, stock full, skipping")
            return

        contract_price = contract.mid or contract.ask or 0
        logger.info(
            f"Option contract: {contract.symbol}, strike={contract.strike}, "
            f"mid={contract.mid}, ask={contract.ask}, delta={contract.delta}"
        )

        account = self.alpaca.get_account()
        equity = account.get("equity", 0) if account else 0
        sizer = OptionsSizer(equity)
        qty = sizer.size_directional(score.total_score, contract_price)
        if qty < 1:
            if self.position_mgr.can_open_position():
                logger.info(f"Options size too small for {ticker}, falling back to stock")
                self._execute_trade(signal, score, price, indicators)
            else:
                logger.info(f"Options size too small for {ticker}, stock full, skipping")
            return

        success = self.options_position_mgr.open_directional(
            contract, qty, score.total_score, price
        )
        if success:
            get_trade_history().record_option_open(
                symbol=contract.symbol,
                strategy="directional",
                qty=qty,
                entry_price=contract.mid or 0,
                score=score.total_score,
                rationale=signal.rationale or "",
                option_details={
                    "underlying": ticker,
                    "strike": contract.strike,
                    "expiration": contract.expiration,
                    "type": contract.option_type,
                    "delta": contract.delta,
                },
            )
            self.discord.alert(
                "Options Trade",
                f"{contract.option_type.upper()} {ticker} ${contract.strike} "
                f"exp {contract.expiration}, {qty}x @ ${contract_price:.2f}",
                "info",
            )
        else:
            if self.position_mgr.can_open_position():
                logger.info(f"Options order failed for {ticker}, falling back to stock")
                self._execute_trade(signal, score, price, indicators)
            else:
                logger.info(f"Options order failed for {ticker}, stock full, skipping")

    def _execute_spread_trade(self, signal, score, price):
        """Execute a credit spread trade."""
        ticker = signal.ticker
        result = self.contract_selector.find_spread_contracts(
            ticker, signal.direction, price
        )
        if not result:
            logger.info(f"No spread contracts for {ticker}, falling back to stock")
            return

        short_leg, long_leg = result
        account = self.alpaca.get_account()
        equity = account.get("equity", 0) if account else 0
        sizer = OptionsSizer(equity)

        width = abs(short_leg.strike - long_leg.strike)
        credit = (short_leg.mid or 0) - (long_leg.mid or 0)
        qty = sizer.size_credit_spread(score.total_score, width, credit)
        if qty < 1:
            return

        success = self.options_position_mgr.open_credit_spread(
            short_leg, long_leg, qty, score.total_score
        )
        if success:
            get_trade_history().record_option_open(
                symbol=short_leg.symbol,
                strategy="credit_spread",
                qty=qty,
                entry_price=credit,
                score=score.total_score,
                rationale=signal.rationale or "",
                option_details={
                    "underlying": ticker,
                    "short_strike": short_leg.strike,
                    "long_strike": long_leg.strike,
                    "expiration": short_leg.expiration,
                    "type": short_leg.option_type,
                    "credit": credit,
                    "width": width,
                },
            )
            self.discord.alert(
                "Spread Trade",
                f"{ticker} {short_leg.option_type} spread "
                f"${short_leg.strike}/${long_leg.strike}, {qty}x, credit=${credit:.2f}",
                "info",
            )

    def _scan_covered_calls(self):
        """Scan profitable stock positions with 100+ shares for covered calls."""
        if not self.options_position_mgr.can_open():
            return

        positions = self.alpaca.get_positions()
        for p in positions:
            symbol = p["symbol"]
            qty = int(p["qty"])
            if qty < 100:
                continue
            if self.options_position_mgr.has_covered_call(symbol):
                continue
            # Only write calls on profitable positions
            if p["unrealized_pl"] <= 0:
                continue

            price = p["current_price"]
            contract = self.contract_selector.find_covered_call_contract(
                symbol, price, qty
            )
            if not contract:
                continue

            sizer = OptionsSizer(0)  # equity not needed for CC sizing
            cc_qty = sizer.size_covered_call(qty)
            if cc_qty < 1:
                continue

            success = self.options_position_mgr.open_covered_call(
                contract, cc_qty, p["avg_entry"]
            )
            if success:
                get_trade_history().record_option_open(
                    symbol=contract.symbol,
                    strategy="covered_call",
                    qty=cc_qty,
                    entry_price=contract.mid or 0,
                    score=0,
                    rationale=f"Covered call on {symbol}",
                    option_details={
                        "underlying": symbol,
                        "strike": contract.strike,
                        "expiration": contract.expiration,
                    },
                )
                self.discord.alert(
                    "Covered Call",
                    f"Sold {cc_qty}x {symbol} ${contract.strike} call exp {contract.expiration}",
                    "info",
                )
                if not self.options_position_mgr.can_open():
                    break

    def _check_options_positions(self):
        """Check options positions for exit triggers."""
        def get_option_price(symbol):
            """Get current price for an option or stock symbol."""
            price = self.market_data.get_current_price(symbol)
            return price

        closed = self.options_position_mgr.check_exits(get_option_price)
        for key in closed:
            logger.info(f"Options position closed: {key}")
            get_trade_history().record_option_close(key, 0, "exit_trigger")

    def _send_daily_summary(self):
        """Send end of day summary."""
        summary = self.risk_mgr.get_daily_summary()
        self.discord.daily_summary(summary)
        logger.info(f"Daily summary: {summary}")


def main():
    parser = argparse.ArgumentParser(description="Autonomous Day Trading Bot")
    parser.add_argument(
        "--paper",
        action="store_true",
        default=True,
        help="Use paper trading (default: True)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live trading (CAUTION!)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show market status and exit",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--usage",
        action="store_true",
        help="Show API usage stats and exit",
    )
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level=level)

    if args.usage:
        from src.signals.usage_tracker import get_tracker
        tracker = get_tracker()
        today = tracker.get_today_summary()
        total = tracker.get_total_summary()
        print("=== Grok API Usage ===")
        print(f"Today ({today['date']}):")
        print(f"  Requests: {today['requests']}")
        print(f"  Tokens: {today['input_tokens']:,} in / {today['output_tokens']:,} out")
        print(f"  Cost: ${today['cost']:.4f}")
        print(f"  Signals: {today['signals']}")
        print(f"\nAll Time:")
        print(f"  Total requests: {total['total_requests']}")
        print(f"  Total cost: ${total['total_cost']:.4f}")
        print(f"  Days tracked: {total['days_tracked']}")
        return

    if args.status:
        print(format_market_status())
        account = AlpacaClient().get_account()
        if account:
            print(f"Equity: ${account.get('equity', 0):,.2f}")
            print(f"Buying Power: ${account.get('buying_power', 0):,.2f}")
        return

    # Override mode from CLI args
    if args.live:
        import config.settings as cfg
        cfg.TRADING_MODE = "live"
        cfg.ALPACA_API_KEY = cfg.ALPACA_LIVE_API_KEY
        cfg.ALPACA_SECRET_KEY = cfg.ALPACA_LIVE_SECRET_KEY
        cfg.ALPACA_BASE_URL = "https://api.alpaca.markets"
        cfg.PAPER_TRADING_24_7 = False

    paper = settings.is_paper_mode()

    if not paper and not os.environ.get("SKIP_LIVE_CONFIRM"):
        print("\n" + "="*50)
        print("⚠️  WARNING: LIVE TRADING MODE")
        print("="*50)
        print(f"API Key: {settings.ALPACA_API_KEY[:8]}...")
        print(f"Day Trade Limit: {settings.DAY_TRADE_LIMIT} per 5 days")
        print("="*50 + "\n")
        confirm = input("Type 'YES I UNDERSTAND' to confirm: ")
        if confirm != "YES I UNDERSTAND":
            print("Aborted.")
            return

    # Verify API keys
    if not settings.GROK_API_KEY:
        logger.error("GROK_API_KEY not set")
        sys.exit(1)
    if not settings.ALPACA_API_KEY:
        logger.error("ALPACA_API_KEY not set")
        sys.exit(1)

    # Acquire lock to prevent multiple instances
    if not acquire_lock():
        logger.error("Failed to acquire lock - exiting")
        sys.exit(1)

    bot = TradingBot(paper=paper)
    bot.run()


if __name__ == "__main__":
    main()
