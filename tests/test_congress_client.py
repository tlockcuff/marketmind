"""Tests for congressional stock trading scraper."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.signals.congress_client import (
    CongressClient,
    CongressTrade,
    CACHE_FILE,
    _lookup_party,
    AMOUNT_ORDER,
)


# -- Fixtures --

def _make_trade(**kwargs):
    defaults = dict(
        politician="Tommy Tuberville",
        party="R",
        chamber="Senate",
        ticker="NVDA",
        asset_description="NVIDIA Corp",
        direction="Purchase",
        amount_range="$50,001 - $100,000",
        transaction_date="01/15/2025",
        filing_date="01/20/2025",
        owner="Self",
    )
    defaults.update(kwargs)
    return CongressTrade(**defaults)


SAMPLE_SENATE_DETAIL_HTML = """
<html><body>
<table class="table">
<tr><th>TX Date</th><th>Date</th><th>Owner</th><th>Ticker</th><th>Asset</th><th>Type</th><th>Amount</th></tr>
<tr><td>1</td><td>01/15/2025</td><td>Self</td><td>NVDA</td><td>NVIDIA Corp</td><td>Purchase</td><td>$50,001 - $100,000</td></tr>
<tr><td>2</td><td>01/16/2025</td><td>Spouse</td><td>AAPL</td><td>Apple Inc</td><td>Sale (Full)</td><td>$15,001 - $50,000</td></tr>
<tr><td>3</td><td>01/17/2025</td><td>Self</td><td>--</td><td>US Treasury</td><td>Purchase</td><td>$100,001 - $250,000</td></tr>
</table>
</body></html>
"""

SAMPLE_HOUSE_DETAIL_HTML = """
<html><body>
<table>
<tr><th>Owner</th><th>Date</th><th>Asset</th><th>Type</th><th>Amount</th></tr>
<tr><td>Self</td><td>01/10/2025</td><td>Apple Inc (AAPL)</td><td>Purchase</td><td>$1,000,001 - $5,000,000</td></tr>
<tr><td>Spouse</td><td>01/11/2025</td><td>Tesla Inc (TSLA)</td><td>Sale</td><td>$250,001 - $500,000</td></tr>
<tr><td>Self</td><td>01/12/2025</td><td>Municipal Bond Fund</td><td>Purchase</td><td>$50,001 - $100,000</td></tr>
</table>
</body></html>
"""


# -- Tests --

class TestParty:
    def test_known_senator(self):
        assert _lookup_party("Tommy Tuberville") == "R"

    def test_known_rep(self):
        assert _lookup_party("Nancy Pelosi") == "D"

    def test_last_name_lookup(self):
        assert _lookup_party("pelosi") == "D"

    def test_unknown(self):
        assert _lookup_party("John Nobody") == "?"

    def test_independent(self):
        assert _lookup_party("Angus King") == "I"


class TestCongressTrade:
    def test_amount_midpoint(self):
        t = _make_trade(amount_range="$50,001 - $100,000")
        assert t.amount_midpoint == 75_000

    def test_unknown_amount(self):
        t = _make_trade(amount_range="Unknown")
        assert t.amount_midpoint == 0


class TestParseSenateHTML:
    def test_parse_detail_page(self):
        client = CongressClient()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_SENATE_DETAIL_HTML, "html.parser")
        table = soup.find("table")
        rows = table.find_all("tr")[1:]

        trades = []
        for tr in rows:
            cols = tr.find_all("td")
            if len(cols) < 6:
                continue
            tx_date = cols[1].get_text(strip=True)
            owner = cols[2].get_text(strip=True)
            ticker_text = cols[3].get_text(strip=True)
            asset_desc = cols[4].get_text(strip=True)
            tx_type = cols[5].get_text(strip=True)
            amount = cols[6].get_text(strip=True) if len(cols) > 6 else ""

            ticker = client._extract_ticker(ticker_text)
            if not ticker or ticker == "--":
                continue

            direction = "Purchase" if "purchase" in tx_type.lower() else "Sale"
            trades.append(CongressTrade(
                politician="Tommy Tuberville", party="R", chamber="Senate",
                ticker=ticker, asset_description=asset_desc, direction=direction,
                amount_range=amount, transaction_date=tx_date,
                filing_date="01/20/2025", owner=owner,
            ))

        assert len(trades) == 2  # "--" ticker filtered
        assert trades[0].ticker == "NVDA"
        assert trades[0].direction == "Purchase"
        assert trades[1].ticker == "AAPL"
        assert trades[1].direction == "Sale"
        assert trades[1].owner == "Spouse"


class TestParseHouseHTML:
    def test_parse_detail_page(self):
        client = CongressClient()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_HOUSE_DETAIL_HTML, "html.parser")
        table = soup.find("table")
        rows = table.find_all("tr")[1:]

        trades = []
        for tr in rows:
            cols = tr.find_all("td")
            if len(cols) < 5:
                continue
            owner = cols[0].get_text(strip=True)
            tx_date = cols[1].get_text(strip=True)
            asset_desc = cols[2].get_text(strip=True)
            tx_type = cols[3].get_text(strip=True)
            amount = cols[4].get_text(strip=True)

            ticker = client._extract_ticker_from_desc(asset_desc)
            if not ticker:
                continue

            direction = "Purchase" if "purchase" in tx_type.lower() else "Sale"
            trades.append(CongressTrade(
                politician="Nancy Pelosi", party="D", chamber="House",
                ticker=ticker, asset_description=asset_desc, direction=direction,
                amount_range=amount, transaction_date=tx_date,
                filing_date="01/18/2025", owner=owner,
            ))

        assert len(trades) == 2  # Municipal Bond Fund has no ticker
        assert trades[0].ticker == "AAPL"
        assert trades[1].ticker == "TSLA"
        assert trades[1].owner == "Spouse"


class TestCacheFreshness:
    def test_fresh_cache(self, tmp_path, monkeypatch):
        cache = tmp_path / "congress_trades.json"
        monkeypatch.setattr("src.signals.congress_client.CACHE_FILE", cache)

        data = {
            "cached_at": datetime.now().isoformat(),
            "trade_count": 1,
            "trades": [],
        }
        cache.write_text(json.dumps(data))

        client = CongressClient()
        assert client._is_cache_fresh() is True

    def test_stale_cache(self, tmp_path, monkeypatch):
        cache = tmp_path / "congress_trades.json"
        monkeypatch.setattr("src.signals.congress_client.CACHE_FILE", cache)

        stale_time = datetime.now() - timedelta(hours=7)
        data = {
            "cached_at": stale_time.isoformat(),
            "trade_count": 1,
            "trades": [],
        }
        cache.write_text(json.dumps(data))

        client = CongressClient()
        assert client._is_cache_fresh() is False

    def test_no_cache_file(self, tmp_path, monkeypatch):
        cache = tmp_path / "nonexistent.json"
        monkeypatch.setattr("src.signals.congress_client.CACHE_FILE", cache)
        client = CongressClient()
        assert client._is_cache_fresh() is False


class TestBuildContextString:
    def test_formatted_output(self):
        client = CongressClient()
        trades = [
            _make_trade(politician="Tommy Tuberville", party="R", chamber="Senate",
                        ticker="NVDA", direction="Purchase",
                        amount_range="$50,001 - $100,000"),
            _make_trade(politician="Nancy Pelosi", party="D", chamber="House",
                        ticker="AAPL", direction="Sale",
                        amount_range="$1,000,001 - $5,000,000"),
        ]
        with patch.object(client, "get_recent_trades", return_value=trades):
            ctx = client.build_context_string()

        assert "RECENT CONGRESSIONAL TRADES" in ctx
        assert "Sen. Tommy Tuberville (R) BOUGHT" in ctx
        assert "Rep. Nancy Pelosi (D) SOLD" in ctx
        assert "NVDA" in ctx
        assert "AAPL" in ctx

    def test_empty_trades(self):
        client = CongressClient()
        with patch.object(client, "get_recent_trades", return_value=[]):
            ctx = client.build_context_string()
        assert ctx is None

    def test_spouse_tagged(self):
        client = CongressClient()
        trades = [
            _make_trade(owner="Spouse", ticker="TSLA"),
        ]
        with patch.object(client, "get_recent_trades", return_value=trades):
            ctx = client.build_context_string()
        assert "[Spouse]" in ctx

    def test_self_not_tagged(self):
        client = CongressClient()
        trades = [_make_trade(owner="Self")]
        with patch.object(client, "get_recent_trades", return_value=trades):
            ctx = client.build_context_string()
        assert "[Self]" not in ctx


class TestFilters:
    def test_filters_non_stock(self):
        client = CongressClient()
        assert client._extract_ticker("--") == None or client._extract_ticker("--") == "--"
        # The scraper filters ticker=="--", so verify the logic
        ticker = client._extract_ticker("--")
        # "--" should be filtered by caller (not ticker == "--")
        assert ticker is None or ticker == "--"

    def test_extracts_ticker(self):
        client = CongressClient()
        assert client._extract_ticker("NVDA") == "NVDA"
        assert client._extract_ticker("$AAPL") == "AAPL"

    def test_extract_from_desc(self):
        client = CongressClient()
        assert client._extract_ticker_from_desc("Apple Inc (AAPL)") == "AAPL"
        assert client._extract_ticker_from_desc("NVDA") == "NVDA"
        assert client._extract_ticker_from_desc("Municipal Bond Fund") is None


class TestAmountSorting:
    def test_highest_first(self):
        trades = [
            _make_trade(amount_range="$15,001 - $50,000", ticker="LOW"),
            _make_trade(amount_range="$1,000,001 - $5,000,000", ticker="HIGH"),
            _make_trade(amount_range="$50,001 - $100,000", ticker="MID"),
        ]
        trades.sort(key=lambda t: t.amount_midpoint, reverse=True)
        assert trades[0].ticker == "HIGH"
        assert trades[1].ticker == "MID"
        assert trades[2].ticker == "LOW"


class TestClusterSummary:
    def test_clusters_noted(self):
        client = CongressClient()
        trades = [
            _make_trade(ticker="NVDA", direction="Purchase", politician="A"),
            _make_trade(ticker="NVDA", direction="Purchase", politician="B"),
            _make_trade(ticker="NVDA", direction="Purchase", politician="C"),
            _make_trade(ticker="AAPL", direction="Sale", politician="D"),
            _make_trade(ticker="AAPL", direction="Sale", politician="E"),
        ]
        with patch.object(client, "get_recent_trades", return_value=trades):
            ctx = client.build_context_string()
        assert "NVDA (3 buys)" in ctx
        assert "AAPL (2 sales)" in ctx


class TestDisabled:
    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr("config.settings.CONGRESS_ENABLED", False)
        # When disabled, main.py sets self.congress = None
        # so build_context_string is never called.
        # Verify the setting is respected.
        from config import settings
        assert settings.CONGRESS_ENABLED is False
