import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from config import settings

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    def __init__(self):
        self.alpaca_client = None
        if settings.ALPACA_API_KEY and settings.ALPACA_SECRET_KEY:
            self.alpaca_client = StockHistoricalDataClient(
                settings.ALPACA_API_KEY,
                settings.ALPACA_SECRET_KEY,
            )

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

    def _fetch_alpaca(
        self,
        ticker: str,
        days: int,
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        if not self.alpaca_client:
            return None
        try:
            tf_map = {
                "1m": TimeFrame.Minute,
                "5m": TimeFrame(5, "Min"),
                "15m": TimeFrame(15, "Min"),
                "1h": TimeFrame.Hour,
                "1d": TimeFrame.Day,
            }
            tf = tf_map.get(timeframe, TimeFrame.Day)
            end = datetime.now()
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
        except Exception as e:
            logger.warning(f"Alpaca fetch failed for {ticker}: {e}")
            return None

    def _fetch_yfinance(
        self,
        ticker: str,
        days: int,
        timeframe: str,
    ) -> Optional[pd.DataFrame]:
        try:
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
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            logger.warning(f"yfinance fetch failed for {ticker}: {e}")
            return None

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get latest price for ticker."""
        try:
            stock = yf.Ticker(ticker)
            return stock.info.get("regularMarketPrice") or stock.info.get("currentPrice")
        except Exception as e:
            logger.warning(f"Failed to get price for {ticker}: {e}")
            return None

    def get_market_context(self) -> Optional[str]:
        """Get broad market context: SPY/QQQ, VIX, sector ETFs."""
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
                return "CURRENT MARKET:\n" + "\n".join(context_parts)
            return None
        except Exception as e:
            logger.warning(f"Failed to get market context: {e}")
            return None

    def get_market_regime(self) -> dict:
        """Determine market regime from SPY trend + VIX.

        Returns dict with 'regime' (trending_up, trending_down, choppy, high_volatility)
        and 'vix' level.
        """
        result = {"regime": "choppy", "vix": None}
        try:
            # VIX
            vix = yf.Ticker("^VIX")
            vix_price = vix.info.get("regularMarketPrice")
            result["vix"] = vix_price

            if vix_price and vix_price > 30:
                result["regime"] = "high_volatility"
                return result

            # SPY SMA5 vs SMA20 for trend
            spy = yf.Ticker("SPY")
            hist = spy.history(period="30d", interval="1d")
            if hist is not None and len(hist) >= 20:
                close = hist["Close"]
                sma5 = close.rolling(5).mean().iloc[-1]
                sma20 = close.rolling(20).mean().iloc[-1]

                if sma5 > sma20 * 1.005:
                    result["regime"] = "trending_up"
                elif sma5 < sma20 * 0.995:
                    result["regime"] = "trending_down"
                else:
                    result["regime"] = "choppy"
        except Exception as e:
            logger.warning(f"Failed to get market regime: {e}")

        return result

    def get_quote(self, ticker: str) -> Optional[dict]:
        """Get current quote with bid/ask."""
        try:
            stock = yf.Ticker(ticker)
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
