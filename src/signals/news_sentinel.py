"""News Sentinel — real-time headline monitor for portfolio protection.

Polls Alpaca news API for held symbols, classifies headlines via keyword
matching, and queues protective actions (tighten stop, trim, emergency exit)
for the main trading loop to drain.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from queue import Queue
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class Severity(Enum):
    INFO = "info"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HeadlineSentiment:
    """Result of classifying a single headline."""
    headline: str
    symbol: str
    severity: Severity
    matched_keyword: str
    source: str = ""
    url: str = ""
    created_at: str = ""


@dataclass
class NewsAction:
    """Queued protective action for the main loop to execute."""
    symbol: str
    severity: Severity
    action: str  # "tighten_stop", "trim", "emergency_exit", "log_only"
    headline: str
    matched_keyword: str
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Keyword classifier
# ---------------------------------------------------------------------------

class KeywordClassifier:
    """Classify headlines by keyword matching against severity tiers."""

    CRITICAL_KEYWORDS = [
        "fda rejects", "sec charges", "bankruptcy", "fraud", "delisted",
        "halted", "criminal", "indicted", "default", "liquidat",
    ]

    WARNING_KEYWORDS = [
        "downgrade", "misses estimates", "guidance cut", "cfo resigns",
        "recall", "lawsuit", "investigation", "layoffs", "revenue miss",
        "earnings miss", "profit warning", "class action",
    ]

    CAUTION_KEYWORDS = [
        "volatility", "under review", "analyst concern", "short interest",
        "overvalued", "price target cut", "sells stake", "insider sell",
        "bearish", "headwinds",
    ]

    def classify(self, headline: str, symbol: str) -> Optional[HeadlineSentiment]:
        """Return HeadlineSentiment if headline matches any keyword, else None."""
        hl = headline.lower()

        for kw in self.CRITICAL_KEYWORDS:
            if kw in hl:
                return HeadlineSentiment(
                    headline=headline, symbol=symbol,
                    severity=Severity.CRITICAL, matched_keyword=kw,
                )

        for kw in self.WARNING_KEYWORDS:
            if kw in hl:
                return HeadlineSentiment(
                    headline=headline, symbol=symbol,
                    severity=Severity.WARNING, matched_keyword=kw,
                )

        for kw in self.CAUTION_KEYWORDS:
            if kw in hl:
                return HeadlineSentiment(
                    headline=headline, symbol=symbol,
                    severity=Severity.CAUTION, matched_keyword=kw,
                )

        return None


# ---------------------------------------------------------------------------
# Severity → action mapping
# ---------------------------------------------------------------------------

_SEVERITY_ACTION = {
    Severity.CRITICAL: "emergency_exit",
    Severity.WARNING: "trim",
    Severity.CAUTION: "tighten_stop",
    Severity.INFO: "log_only",
}


# ---------------------------------------------------------------------------
# NewsSentinel
# ---------------------------------------------------------------------------

class NewsSentinel:
    """Background daemon that polls news for portfolio symbols and queues actions."""

    def __init__(self, get_symbols_fn=None):
        """
        Args:
            get_symbols_fn: callable returning list[str] of currently held symbols.
                            If None, sentinel does nothing.
        """
        self.get_symbols = get_symbols_fn
        self.classifier = KeywordClassifier()
        self.action_queue: Queue[NewsAction] = Queue()
        self._seen_headlines: set[str] = set()
        self._max_seen = 5000  # cap dedup set size
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # -- public API ----------------------------------------------------------

    def start(self):
        """Start polling in a daemon thread."""
        if not settings.get("news_sentinel_enabled"):
            logger.info("NewsSentinel disabled via config")
            return
        if self._thread and self._thread.is_alive():
            logger.warning("NewsSentinel already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="news-sentinel")
        self._thread.start()
        logger.info("NewsSentinel started")

    def stop(self):
        """Signal the polling loop to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
            logger.info("NewsSentinel stopped")

    def drain_actions(self) -> list[NewsAction]:
        """Drain all queued actions (called from main loop)."""
        actions: list[NewsAction] = []
        while not self.action_queue.empty():
            try:
                actions.append(self.action_queue.get_nowait())
            except Exception:
                break
        return actions

    # -- internal ------------------------------------------------------------

    def _run(self):
        """Polling loop — runs in daemon thread."""
        interval = settings.get("news_sentinel_interval") or 60
        logger.info(f"NewsSentinel polling every {interval}s")

        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as e:
                logger.error(f"NewsSentinel poll error: {e}", exc_info=True)
            self._stop_event.wait(timeout=interval)

    def _poll_once(self):
        """Fetch news for held symbols, classify, queue actions."""
        if not self.get_symbols:
            return
        symbols = self.get_symbols()
        if not symbols:
            return

        articles = self._fetch_news_for_symbols(symbols)
        for article in articles:
            headline = article.get("headline", "")
            dedup_key = headline.lower()[:80]
            if dedup_key in self._seen_headlines:
                continue

            self._seen_headlines.add(dedup_key)
            if len(self._seen_headlines) > self._max_seen:
                # Trim oldest half (set has no order, just clear)
                self._seen_headlines.clear()

            article_symbols = [s.upper() for s in article.get("symbols", [])]
            # Match against held symbols
            matched = [s for s in symbols if s in article_symbols]
            if not matched:
                # Check if headline mentions symbol text
                hl_upper = headline.upper()
                matched = [s for s in symbols if f" {s} " in f" {hl_upper} "]
            if not matched:
                continue

            for sym in matched:
                sentiment = self.classifier.classify(headline, sym)
                if sentiment is None:
                    continue

                sentiment.source = article.get("source", "")
                sentiment.url = article.get("url", "")
                sentiment.created_at = article.get("created_at", "")

                action = NewsAction(
                    symbol=sym,
                    severity=sentiment.severity,
                    action=_SEVERITY_ACTION[sentiment.severity],
                    headline=headline,
                    matched_keyword=sentiment.matched_keyword,
                )
                self.action_queue.put(action)
                logger.warning(
                    f"NewsSentinel [{sentiment.severity.value}] {sym}: "
                    f"'{headline[:80]}' → {action.action} (kw: {sentiment.matched_keyword})"
                )

    def _fetch_news_for_symbols(self, symbols: list[str]) -> list[dict]:
        """Fetch recent news from Alpaca for given symbols."""
        try:
            from alpaca.data.historical.news import NewsClient
            from alpaca.data.requests import NewsRequest
            from datetime import timedelta

            key, secret = self._get_api_keys()
            client = NewsClient(api_key=key, secret_key=secret)
            now_utc = datetime.now(timezone.utc)

            request = NewsRequest(
                symbols=symbols,
                start=now_utc - timedelta(hours=1),
                end=now_utc,
                limit=50,
                sort="desc",
            )
            response = client.get_news(request)
            articles = []
            for item in response.data.get("news", []):
                item_symbols = [s for s in (item.symbols or [])]
                articles.append({
                    "headline": item.headline,
                    "summary": item.summary or "",
                    "source": item.source,
                    "url": item.url,
                    "symbols": item_symbols,
                    "created_at": item.created_at.isoformat() if item.created_at else "",
                })
            return articles
        except Exception as e:
            logger.error(f"NewsSentinel news fetch failed: {e}")
            return []

    @staticmethod
    def _get_api_keys() -> tuple[str, str]:
        """Resolve Alpaca API keys (same logic as news_provider)."""
        if settings.is_paper_mode():
            return settings.ALPACA_PAPER_API_KEY, settings.ALPACA_PAPER_SECRET_KEY
        return settings.ALPACA_LIVE_API_KEY, settings.ALPACA_LIVE_SECRET_KEY
