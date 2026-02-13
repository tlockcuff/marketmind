import functools
import logging
import time
from datetime import datetime, timedelta
from src.utils import utcnow
from typing import Optional

import pandas as pd
import yfinance as yf
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame

from config import settings

logger = logging.getLogger(__name__)


def retry_api_call(max_retries=3, base_delay=1.0, exceptions=(Exception,)):
    """Decorator: retry with exponential backoff for transient API failures."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"retry {func.__name__} attempt {attempt+1} failed: {e}, retrying in {delay:.1f}s")
                        time.sleep(delay)
            logger.error(f"{func.__name__} failed after {max_retries} attempts: {last_exception}")
            return None
        return wrapper
    return decorator


class MarketDataFetcher:
    def __init__(self):
        self.alpaca_client = None
        if settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY:
            self.alpaca_client = StockHistoricalDataClient(
                settings.ALPACA_API_KEY,
                settings.ALPACA_SECRET_KEY,
            )
        # Market context caching
        self._market_context_cache = None
        self._market_context_time = None
        self._market_regime_cache = None
        self._market_regime_time = None

    def get_bars(
        self,
        ticker: str,
        days: int = 30,
        timeframe: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """Fetch historical bars. Try Alpaca first, fallback to yfinance."""
        logger.info(f"Fetching {days}d bars for {ticker}...")
        df = self._fetch_alpaca(ticker, days, timeframe)
        if df is None or df.empty:
            logger.info(f"Alpaca empty for {ticker}, trying yfinance...")
            df = self._fetch_yfinance(ticker, days, timeframe)
        if df is not None and not df.empty:
            logger.info(f"Got {len(df)} bars for {ticker}")
        return df

    @retry_api_call(max_retries=2, base_delay=1.0)
    def _fetch_alpaca(
        self,
        ticker: str,
        days: int,
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        if not self.alpaca_client:
            return None
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
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=tf,
            start=start,
            end=end,
        )
        bars = self.alpaca_client.get_stock_bars(request)
        df = bars.df
        if ticker in df.index.get_level_values(0):
            df = df.loc[ticker]
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        return df

    @staticmethod
    def _yf_symbol(ticker: str) -> str:
        """Convert Alpaca crypto symbols to yfinance format.
        Alpaca: BTCUSD, ETHUSD, AVAXUSD  →  yfinance: BTC-USD, ETH-USD, AVAX-USD"""
        # Handle slash format (BTC/USD → BTC-USD)
        if "/" in ticker:
            return ticker.replace("/", "-")
        # Handle Alpaca no-slash format (BTCUSD → BTC-USD)
        crypto_bases = ["BTC", "ETH", "SOL", "AVAX", "DOGE", "LINK", "ADA",
                        "DOT", "MATIC", "UNI", "AAVE", "SHIB", "XRP", "LTC"]
        for base in crypto_bases:
            if ticker == f"{base}USD":
                return f"{base}-USD"
        return ticker

    @retry_api_call(max_retries=2, base_delay=1.0)
    def _fetch_yfinance(
        self,
        ticker: str,
        days: int,
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "1d": "1d",
        }
        interval = interval_map.get(timeframe, "1d")
        period = f"{days}d" if days <= 60 else f"{days // 30}mo"
        if interval in ["1m", "5m", "15m"] and days > 7:
            period = "7d"
        yf_ticker = self._yf_symbol(ticker)
        stock = yf.Ticker(yf_ticker)
        df = stock.history(period=period, interval=interval)
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        return df

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get latest price for ticker."""
        # Try Alpaca snapshot first
        if self.alpaca_client:
            try:
                request = StockSnapshotRequest(symbol_or_symbols=[ticker])
                snapshots = self.alpaca_client.get_stock_snapshot(request)

                # Handle both dict and direct snapshot return
                snap = snapshots.get(ticker) if isinstance(snapshots, dict) else snapshots
                if snap and snap.latest_trade and snap.latest_trade.price:
                    return snap.latest_trade.price
                else:
                    logger.debug(f"Alpaca snapshot for {ticker} missing trade data, falling back to yfinance")
            except Exception as e:
                logger.debug(f"Alpaca snapshot failed for {ticker}: {e}, falling back to yfinance")

        # Fallback to yfinance
        try:
            yf_ticker = self._yf_symbol(ticker)
            stock = yf.Ticker(yf_ticker)
            return stock.info.get("regularMarketPrice") or stock.info.get("currentPrice")
        except Exception as e:
            logger.warning(f"Failed to get price for {ticker}: {e}")
            return None

    def get_batch_prices(self, symbols: list[str]) -> dict[str, float]:
        """Fetch current prices for multiple symbols via Alpaca snapshot.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dict mapping symbol to current price
        """
        prices = {}

        # Try Alpaca batch snapshot first
        if self.alpaca_client and symbols:
            try:
                # Alpaca limits to 200 symbols per request
                request = StockSnapshotRequest(symbol_or_symbols=symbols[:200])
                snapshots = self.alpaca_client.get_stock_snapshot(request)

                for symbol, snap in (snapshots or {}).items():
                    if snap and snap.latest_trade and snap.latest_trade.price:
                        prices[symbol] = snap.latest_trade.price
            except Exception as e:
                logger.warning(f"Batch snapshot failed: {e}")

        # Fallback to individual lookups for missing symbols
        missing = set(symbols) - set(prices.keys())
        for symbol in missing:
            price = self.get_current_price(symbol)
            if price:
                prices[symbol] = price

        return prices

    def get_batch_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Fetch full quote data for multiple symbols via Alpaca snapshot.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dict mapping symbol to quote dict (price, bid, ask, volume, avg_volume)
        """
        quotes = {}

        # Try Alpaca batch snapshot first
        if self.alpaca_client and symbols:
            try:
                # Alpaca limits to 200 symbols per request
                request = StockSnapshotRequest(symbol_or_symbols=symbols[:200])
                snapshots = self.alpaca_client.get_stock_snapshot(request)

                for symbol, snap in (snapshots or {}).items():
                    if snap:
                        quote = {
                            "price": snap.latest_trade.price if snap.latest_trade else None,
                            "bid": snap.latest_quote.bid_price if snap.latest_quote else None,
                            "ask": snap.latest_quote.ask_price if snap.latest_quote else None,
                            "volume": snap.daily_bar.volume if snap.daily_bar else None,
                            "avg_volume": None,
                        }
                        quotes[symbol] = quote
            except Exception as e:
                logger.warning(f"Batch quotes failed: {e}")

        # Fallback to individual lookups for missing symbols
        missing = set(symbols) - set(quotes.keys())
        for symbol in missing:
            quote = self.get_quote(symbol)
            if quote:
                quotes[symbol] = quote

        return quotes

    def get_market_context(self) -> Optional[str]:
        """Get broad market context: SPY/QQQ, VIX, sector ETFs."""
        # Check cache (5-minute TTL)
        now = time.time()
        if (self._market_context_cache is not None and
            self._market_context_time is not None and
            now - self._market_context_time < 300):
            return self._market_context_cache

        try:
            context_parts = []
            # Major indices
            for sym in ["SPY", "QQQ"]:
                stock = yf.Ticker(sym)
                info = stock.info
                price = info.get("regularMarketPrice")
                prev = info.get("regularMarketPreviousClose")
                if price and prev:
                    chg = ((price - prev) / prev) * 100
                    context_parts.append(f"{sym}: ${price:.2f} ({chg:+.2f}%)")

            # VIX
            vix = yf.Ticker("^VIX")
            vix_price = vix.info.get("regularMarketPrice")
            if vix_price:
                context_parts.append(f"VIX: {vix_price:.1f}")

            # Sector ETFs
            sectors = {"XLK": "Tech", "XLF": "Financials", "XLE": "Energy",
                        "XLV": "Healthcare", "XLI": "Industrials", "XLY": "Consumer"}
            sector_moves = []
            for etf, name in sectors.items():
                stock = yf.Ticker(etf)
                info = stock.info
                price = info.get("regularMarketPrice")
                prev = info.get("regularMarketPreviousClose")
                if price and prev:
                    chg = ((price - prev) / prev) * 100
                    sector_moves.append(f"{name}({etf}): {chg:+.1f}%")

            if sector_moves:
                context_parts.append("Sectors: " + ", ".join(sector_moves))

            if context_parts:
                result = "CURRENT MARKET:\n" + "\n".join(context_parts)
            else:
                result = None

            # Cache result
            self._market_context_cache = result
            self._market_context_time = time.time()
            return result
        except Exception as e:
            logger.warning(f"Failed to get market context: {e}")
            return None

    def get_market_regime(self) -> dict:
        """Determine market regime from SPY trend + VIX.

        Returns dict with 'regime' (trending_up, trending_down, choppy, high_volatility)
        and 'vix' level.
        """
        # Check cache (5-minute TTL)
        now = time.time()
        if (self._market_regime_cache is not None and
            self._market_regime_time is not None and
            now - self._market_regime_time < 300):
            return self._market_regime_cache

        result = {"regime": "choppy", "vix": None}
        try:
            # VIX
            vix = yf.Ticker("^VIX")
            vix_price = vix.info.get("regularMarketPrice")
            result["vix"] = vix_price

            if vix_price and vix_price > 25:
                result["regime"] = "high_volatility"
                self._market_regime_cache = result
                self._market_regime_time = time.time()
                return result

            # SPY SMA5 vs SMA20 for trend, plus SMA20 level check
            spy = yf.Ticker("SPY")
            hist = spy.history(period="30d", interval="1d")
            if hist is not None and len(hist) >= 20:
                close = hist["Close"]
                sma5 = close.rolling(5).mean().iloc[-1]
                sma20 = close.rolling(20).mean().iloc[-1]
                current_close = close.iloc[-1]

                # If SPY is below its 20-day SMA, bias toward trending_down
                if current_close < sma20:
                    if sma5 < sma20 * 0.995:
                        result["regime"] = "trending_down"
                    else:
                        result["regime"] = "trending_down"  # below SMA20 = bearish bias
                elif sma5 > sma20 * 1.005:
                    result["regime"] = "trending_up"
                elif sma5 < sma20 * 0.995:
                    result["regime"] = "trending_down"
                else:
                    result["regime"] = "choppy"
        except Exception as e:
            logger.warning(f"Failed to get market regime: {e}")

        # Cache result
        self._market_regime_cache = result
        self._market_regime_time = time.time()
        return result

    def get_quote(self, ticker: str) -> Optional[dict]:
        """Get current quote with bid/ask."""
        # Try Alpaca snapshot first
        if self.alpaca_client:
            try:
                request = StockSnapshotRequest(symbol_or_symbols=[ticker])
                snapshots = self.alpaca_client.get_stock_snapshot(request)

                # Handle both dict and direct snapshot return
                snap = snapshots.get(ticker) if isinstance(snapshots, dict) else snapshots
                if snap:
                    return {
                        "price": snap.latest_trade.price if snap.latest_trade else None,
                        "bid": snap.latest_quote.bid_price if snap.latest_quote else None,
                        "ask": snap.latest_quote.ask_price if snap.latest_quote else None,
                        "volume": snap.daily_bar.volume if snap.daily_bar else None,
                        "avg_volume": None,
                    }
                else:
                    logger.debug(f"Alpaca snapshot for {ticker} returned no data, falling back to yfinance")
            except Exception as e:
                logger.debug(f"Alpaca snapshot failed for {ticker}: {e}, falling back to yfinance")

        # Fallback to yfinance
        try:
            yf_ticker = self._yf_symbol(ticker)
            stock = yf.Ticker(yf_ticker)
            info = stock.info
            return {
                "price": info.get("regularMarketPrice"),
                "bid": info.get("bid"),
                "ask": info.get("ask"),
                "volume": info.get("regularMarketVolume"),
                "avg_volume": info.get("averageVolume"),
            }
        except Exception as e:
            logger.warning(f"Failed to get quote for {ticker}: {e}")
            return None

    def get_bars_mtf(
        self,
        ticker: str,
        timeframes: Optional[list[tuple[str, int]]] = None,
    ) -> dict[str, Optional[pd.DataFrame]]:
        """Fetch multi-timeframe bars for MTF analysis.

        Args:
            ticker: Stock symbol
            timeframes: List of (timeframe, days) tuples. Defaults to [("1h", 30), ("4h", 60), ("1d", 90)]

        Returns:
            Dict mapping timeframe to DataFrame
        """
        if timeframes is None:
            timeframes = [("1h", 30), ("4h", 60), ("1d", 90)]

        result = {}
        for tf, days in timeframes:
            logger.info(f"Fetching MTF {tf} bars for {ticker}...")
            df = self.get_bars(ticker, days=days, timeframe=tf)
            result[tf] = df

        return result
