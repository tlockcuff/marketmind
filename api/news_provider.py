"""News provider - fetches market news from Alpaca + Finnhub with sector tagging."""

from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests as http_requests
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest

from config import settings

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

logger = logging.getLogger(__name__)

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "GOOG", "META", "AMZN", "NVDA", "TSM", "AVGO", "ORCL",
                   "CRM", "ADBE", "AMD", "INTC", "QCOM", "CSCO", "IBM", "NOW", "SNOW", "PLTR",
                   "NET", "DDOG", "MDB", "CRWD", "ZS", "PANW", "FTNT", "SQ", "SHOP", "UBER"],
    "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT", "DHR", "BMY",
                   "AMGN", "GILD", "ISRG", "MDT", "CVS", "CI", "HUM", "MRNA", "REGN", "VRTX"],
    "Finance": ["JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "V",
                "MA", "PYPL", "COF", "USB", "PNC", "TFC", "BK", "STT", "ICE", "CME"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "DVN",
               "HAL", "BKR", "FANG", "HES", "KMI", "WMB", "OKE", "LNG", "ENPH", "FSLR"],
    "Consumer": ["WMT", "PG", "KO", "PEP", "COST", "HD", "MCD", "NKE", "SBUX", "TGT",
                 "LOW", "TJX", "DG", "DLTR", "ROST", "CMG", "YUM", "DPZ", "LULU", "F", "GM", "TSLA"],
    "Crypto": ["BTC", "ETH", "COIN", "MSTR", "MARA", "RIOT", "CLSK", "BITF", "HUT", "CIFR",
               "BTCUSD", "ETHUSD", "BTC/USD", "ETH/USD"],
}

# Reverse map: symbol → sector
_SYMBOL_SECTOR: dict[str, str] = {}
for _sector, _syms in SECTOR_KEYWORDS.items():
    for _s in _syms:
        _SYMBOL_SECTOR[_s] = _sector

# Cache
_cache: dict[str, any] = {"articles": [], "updated_at": 0}
CACHE_TTL = 300  # 5 minutes


def _tag_sector(symbols: list[str], headline: str) -> str:
    """Determine sector from symbols or headline keywords."""
    for sym in symbols:
        s = sym.upper().replace("/", "")
        if s in _SYMBOL_SECTOR:
            return _SYMBOL_SECTOR[s]
    hl = headline.upper()
    sector_hints = {
        "Technology": ["AI ", "CHIP", "SOFTWARE", "CLOUD", "CYBER", "TECH", "SEMICONDUCTOR"],
        "Healthcare": ["DRUG", "FDA", "PHARMA", "BIOTECH", "VACCINE", "HEALTH", "HOSPITAL"],
        "Finance": ["BANK", "FED ", "RATE", "INTEREST", "WALL STREET", "TREASURY", "LOAN"],
        "Energy": ["OIL", "GAS", "CRUDE", "OPEC", "ENERGY", "SOLAR", "RENEWABLE"],
        "Consumer": ["RETAIL", "CONSUMER", "STORE", "SALES", "E-COMMERCE"],
        "Crypto": ["BITCOIN", "CRYPTO", "ETHEREUM", "BLOCKCHAIN", "DEFI"],
    }
    for sector, hints in sector_hints.items():
        if any(h in hl for h in hints):
            return sector
    return "General"


def _get_api_keys() -> tuple[str, str]:
    if settings.is_paper_mode():
        return settings.ALPACA_PAPER_API_KEY, settings.ALPACA_PAPER_SECRET_KEY
    return settings.ALPACA_LIVE_API_KEY, settings.ALPACA_LIVE_SECRET_KEY


def fetch_news(sector: Optional[str] = None, limit: int = 50) -> dict:
    """Fetch news articles, using cache if fresh."""
    now = time.time()
    if now - _cache["updated_at"] < CACHE_TTL and _cache["articles"]:
        articles = _cache["articles"]
    else:
        articles = _fetch_from_api(limit)
        _cache["articles"] = articles
        _cache["updated_at"] = now

    if sector and sector.lower() != "all":
        sector_title = sector.title()
        articles = [a for a in articles if a["sector"] == sector_title]

    sectors = ["Technology", "Healthcare", "Finance", "Energy", "Consumer", "Crypto", "General"]
    return {
        "articles": articles,
        "sectors": sectors,
        "updated_at": datetime.now().isoformat(),
    }


def _fetch_from_api(limit: int) -> list[dict]:
    """Fetch from Alpaca + Finnhub, merge and dedupe."""
    articles = []

    # Alpaca News
    try:
        key, secret = _get_api_keys()
        client = NewsClient(api_key=key, secret_key=secret)
        now_utc = datetime.now(timezone.utc)
        request = NewsRequest(
            start=now_utc - timedelta(days=1),
            end=now_utc,
            limit=min(limit, 50),
            sort="desc",
        )
        response = client.get_news(request)
        for item in response.data.get("news", []):
            symbols = [s for s in (item.symbols or [])]
            articles.append({
                "headline": item.headline,
                "summary": item.summary or "",
                "source": item.source,
                "url": item.url,
                "symbols": symbols,
                "created_at": item.created_at.isoformat() if item.created_at else "",
                "sector": _tag_sector(symbols, item.headline),
            })
        logger.info(f"Alpaca: {len(articles)} articles")
    except Exception as e:
        logger.error(f"Alpaca news fetch failed: {e}")

    # Finnhub News (supplements with more recent articles)
    if FINNHUB_API_KEY:
        try:
            finnhub_articles = _fetch_finnhub(limit)
            # Dedupe by headline similarity
            existing_headlines = {a["headline"].lower()[:60] for a in articles}
            added = 0
            for fa in finnhub_articles:
                if fa["headline"].lower()[:60] not in existing_headlines:
                    articles.append(fa)
                    existing_headlines.add(fa["headline"].lower()[:60])
                    added += 1
            logger.info(f"Finnhub: +{added} unique articles")
        except Exception as e:
            logger.error(f"Finnhub news fetch failed: {e}")

    # Sort all by created_at descending
    articles.sort(key=lambda a: a.get("created_at", ""), reverse=True)

    if not articles:
        return _cache.get("articles", [])
    return articles[:limit]


def _fetch_finnhub(limit: int) -> list[dict]:
    """Fetch general market news from Finnhub."""
    url = "https://finnhub.io/api/v1/news"
    params = {"category": "general", "token": FINNHUB_API_KEY}
    resp = http_requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    articles = []
    for item in data[:limit]:
        dt_str = ""
        if item.get("datetime"):
            dt_str = datetime.fromtimestamp(item["datetime"], tz=timezone.utc).isoformat()
        symbols = item.get("related", "").split(",") if item.get("related") else []
        symbols = [s.strip() for s in symbols if s.strip()]
        articles.append({
            "headline": item.get("headline", ""),
            "summary": item.get("summary", ""),
            "source": item.get("source", "Finnhub"),
            "url": item.get("url", ""),
            "symbols": symbols,
            "created_at": dt_str,
            "sector": _tag_sector(symbols, item.get("headline", "")),
        })
    return articles
