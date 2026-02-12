"""
Scrape congressional stock trading disclosures (Senate + House PTR filings).
Cache results, build context string for Grok prompt injection.

Primary source: Capitol Trades (both chambers, clean HTML tables)
Fallback: House Clerk XML (House PTR filings only)
"""

import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from src.utils import utcnow
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from config import settings
from src.db import get_db

logger = logging.getLogger(__name__)

# Amount ranges ordered for sorting (midpoint estimate)
AMOUNT_ORDER = {
    "$1,001 - $15,000": 8_000,
    "1K–15K": 8_000,
    "$15,001 - $50,000": 32_500,
    "15K–50K": 32_500,
    "$50,001 - $100,000": 75_000,
    "50K–100K": 75_000,
    "$100,001 - $250,000": 175_000,
    "100K–250K": 175_000,
    "$250,001 - $500,000": 375_000,
    "250K–500K": 375_000,
    "$500,001 - $1,000,000": 750_000,
    "500K–1M": 750_000,
    "$1,000,001 - $5,000,000": 3_000_000,
    "1M–5M": 3_000_000,
    "$5,000,001 - $25,000,000": 15_000_000,
    "5M–25M": 15_000_000,
    "$25,000,001 - $50,000,000": 37_500_000,
    "25M–50M": 37_500_000,
    "$50,000,001 +": 75_000_000,
    "50M+": 75_000_000,
    "Over $50,000,000": 75_000_000,
}

# Top ~100 most-active congressional traders (name fragment → party)
# Expand as needed; unknowns logged as "(?)".
PARTY_LOOKUP = {
    # Senate
    "tuberville": "R", "tommy tuberville": "R",
    "sullivan": "R", "dan sullivan": "R",
    "cassidy": "R", "bill cassidy": "R",
    "hagerty": "R", "bill hagerty": "R",
    "ricketts": "R", "pete ricketts": "R",
    "mullin": "R", "markwayne mullin": "R",
    "hoeven": "R", "john hoeven": "R",
    "hyde-smith": "R", "cindy hyde-smith": "R",
    "capito": "R", "shelley moore capito": "R",
    "boozman": "R", "john boozman": "R",
    "crapo": "R", "mike crapo": "R",
    "scott": "R", "tim scott": "R", "rick scott": "R",
    "cruz": "R", "ted cruz": "R",
    "kennedy": "R", "john kennedy": "R",
    "cornyn": "R", "john cornyn": "R",
    "mcconnell": "R", "mitch mcconnell": "R",
    "lummis": "R", "cynthia lummis": "R",
    "britt": "R", "katie britt": "R",
    "king": "I", "angus king": "I",
    "hickenlooper": "D", "john hickenlooper": "D",
    "ossoff": "D", "jon ossoff": "D",
    "kelly": "D", "mark kelly": "D",
    "peters": "D", "gary peters": "D",
    "warner": "D", "mark warner": "D",
    "carper": "D", "tom carper": "D",
    "stabenow": "D", "debbie stabenow": "D",
    "whitehouse": "D", "sheldon whitehouse": "D",
    "bennet": "D", "michael bennet": "D",
    "durbin": "D", "dick durbin": "D",
    "manchin": "D", "joe manchin": "D",
    "sinema": "I", "kyrsten sinema": "I",
    "fetterman": "D", "john fetterman": "D",
    "warnock": "D", "raphael warnock": "D",
    "tester": "D", "jon tester": "D",
    "rosen": "D", "jacky rosen": "D",
    # House
    "pelosi": "D", "nancy pelosi": "D",
    "greene": "R", "marjorie taylor greene": "R",
    "crenshaw": "R", "dan crenshaw": "R",
    "gottheimer": "D", "josh gottheimer": "D",
    "meeks": "D", "gregory meeks": "D",
    "fallon": "R", "pat fallon": "R",
    "mccaul": "R", "michael mccaul": "R",
    "gimenez": "R", "carlos gimenez": "R",
    "ro khanna": "D", "khanna": "D",
    "malinowski": "D", "tom malinowski": "D",
    "wicker": "R", "roger wicker": "R",
    "austin scott": "R",
    "debbie wasserman schultz": "D", "wasserman schultz": "D",
    "kustoff": "R", "david kustoff": "R",
    "nehls": "R", "troy nehls": "R",
    "waltz": "R", "michael waltz": "R",
    "kim": "D", "andy kim": "D",
    "mfume": "D", "kweisi mfume": "D",
    "moore": "D", "gwen moore": "D",
    "boebert": "R", "lauren boebert": "R",
    "casten": "D", "sean casten": "D",
    "cohen": "D", "steve cohen": "D",
    "delbene": "D", "suzan delbene": "D",
    "donalds": "R", "byron donalds": "R",
}


def _lookup_party(name: str) -> str:
    """Lookup party by name fragment. Returns R/D/I or '?'."""
    low = name.strip().lower()
    if low in PARTY_LOOKUP:
        return PARTY_LOOKUP[low]
    # Try last name only
    parts = low.split()
    for part in reversed(parts):
        if part in PARTY_LOOKUP:
            return PARTY_LOOKUP[part]
    logger.debug(f"Unknown party for: {name}")
    return "?"


@dataclass
class CongressTrade:
    politician: str
    party: str
    chamber: str  # "Senate" or "House"
    ticker: str
    asset_description: str
    direction: str  # "Purchase" or "Sale"
    amount_range: str
    transaction_date: str  # YYYY-MM-DD or best effort
    filing_date: str
    owner: str  # "Self", "Spouse", "Joint", "Child", etc.

    @property
    def amount_midpoint(self) -> int:
        return AMOUNT_ORDER.get(self.amount_range, 0)


class CongressClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

    def get_recent_trades(self) -> List[CongressTrade]:
        """Return cached trades if fresh, else scrape."""
        if self._is_cache_fresh():
            cached = self._load_cache()
            if cached is not None:
                return cached

        trades: List[CongressTrade] = []

        # Primary: Capitol Trades (both chambers)
        try:
            ct = self._scrape_capitol_trades()
            trades.extend(ct)
            logger.info(f"Scraped {len(ct)} trades from Capitol Trades")
        except Exception as e:
            logger.warning(f"Capitol Trades scrape failed: {e}")

        # Fallback: House XML (if Capitol Trades got nothing)
        if not trades:
            try:
                house = self._scrape_house_xml()
                trades.extend(house)
                logger.info(f"Scraped {len(house)} House trades from XML")
            except Exception as e:
                logger.warning(f"House XML scrape failed: {e}")

        if trades:
            self._save_cache(trades)
        return trades

    def build_context_string(self) -> Optional[str]:
        """Build formatted context for Grok prompt. Returns None if no data."""
        trades = self.get_recent_trades()
        if not trades:
            return None

        # Sort by amount descending, take top 20
        trades.sort(key=lambda t: t.amount_midpoint, reverse=True)
        top = trades[:20]

        lines = ["RECENT CONGRESSIONAL TRADES (last 30 days):"]
        for t in top:
            chamber = "Sen." if t.chamber == "Senate" else "Rep."
            party = f"({t.party})" if t.party != "?" else "(?)"
            direction = "BOUGHT" if t.direction == "Purchase" else "SOLD"
            owner_tag = f" [{t.owner}]" if t.owner and t.owner != "Self" else ""
            lines.append(
                f"- {chamber} {t.politician} {party} {direction} "
                f"{t.amount_range} {t.ticker} on {t.transaction_date} "
                f"(filed {t.filing_date}){owner_tag}"
            )

        # Cluster summary
        ticker_buys: Counter = Counter()
        ticker_sales: Counter = Counter()
        for t in trades:
            if t.direction == "Purchase":
                ticker_buys[t.ticker] += 1
            else:
                ticker_sales[t.ticker] += 1

        clusters = []
        for ticker, count in ticker_buys.most_common(5):
            if count >= 2:
                clusters.append(f"{ticker} ({count} buys)")
        for ticker, count in ticker_sales.most_common(5):
            if count >= 2:
                clusters.append(f"{ticker} ({count} sales)")
        if clusters:
            lines.append(f"Notable clusters: {', '.join(clusters)}")

        return "\n".join(lines)

    # -- Capitol Trades (primary, both chambers) --

    def _scrape_capitol_trades(self) -> List[CongressTrade]:
        """Scrape capitoltrades.com HTML tables (Senate + House)."""
        trades: List[CongressTrade] = []
        cutoff = utcnow() - timedelta(days=settings.CONGRESS_LOOKBACK_DAYS)

        for page in range(1, 6):  # up to 5 pages
            resp = self.session.get(
                f"https://www.capitoltrades.com/trades?page={page}&pageSize=96",
                timeout=20,
            )
            if resp.status_code != 200:
                logger.warning(f"Capitol Trades page {page}: {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table")
            if not table:
                break

            rows = table.find_all("tr")[1:]  # skip header
            if not rows:
                break

            page_has_old = False
            for tr in rows:
                trade = self._parse_capitol_trades_row(tr)
                if not trade:
                    continue

                # Check if trade is within lookback window
                try:
                    tx_date = datetime.strptime(trade.transaction_date, "%Y-%m-%d")
                    if tx_date < cutoff:
                        page_has_old = True
                        continue
                except (ValueError, TypeError):
                    pass

                trades.append(trade)

            if page_has_old:
                break
            time.sleep(1)

        return trades

    def _parse_capitol_trades_row(self, tr) -> Optional[CongressTrade]:
        """Parse a single row from Capitol Trades table."""
        cols = tr.find_all("td")
        if len(cols) < 8:
            return None

        # Col 0: Politician (name, party, chamber, state)
        pol_cell = cols[0]
        pol_text = pol_cell.get_text(separator="\n", strip=True)
        pol_lines = [l.strip() for l in pol_text.split("\n") if l.strip()]

        if len(pol_lines) < 2:
            return None

        politician = pol_lines[0]
        # Party/chamber from second line: e.g. "Democrat" "House" "TN"
        party_text = pol_lines[1] if len(pol_lines) > 1 else ""
        chamber_text = pol_lines[2] if len(pol_lines) > 2 else ""

        party = "D" if "democrat" in party_text.lower() else \
                "R" if "republican" in party_text.lower() else \
                "I" if "independent" in party_text.lower() else \
                _lookup_party(politician)
        chamber = "Senate" if "senate" in chamber_text.lower() else "House"

        # Col 1: Traded Issuer (company name + ticker)
        issuer_cell = cols[1]
        issuer_text = issuer_cell.get_text(separator="\n", strip=True)
        ticker = self._extract_ticker_from_issuer(issuer_text)
        if not ticker:
            return None
        asset_desc = issuer_text.split("\n")[0] if "\n" in issuer_text else issuer_text

        # Col 2: Published date (ignore, we want traded date)
        # Col 3: Traded date
        traded_text = cols[3].get_text(strip=True)
        tx_date = self._parse_capitol_date(traded_text)

        # Col 4: Filed After (days) — we compute filing date from published
        published_text = cols[2].get_text(strip=True)
        filing_date = self._parse_capitol_date(published_text)

        # Col 5: Owner
        owner = cols[5].get_text(strip=True) or "Self"
        if owner == "Undisclosed":
            owner = "Self"

        # Col 6: Type (buy/sell)
        tx_type = cols[6].get_text(strip=True).lower()
        direction = "Purchase" if "buy" in tx_type else "Sale"

        # Col 7: Size
        amount = cols[7].get_text(strip=True)

        return CongressTrade(
            politician=politician,
            party=party,
            chamber=chamber,
            ticker=ticker,
            asset_description=asset_desc,
            direction=direction,
            amount_range=amount,
            transaction_date=tx_date,
            filing_date=filing_date,
            owner=owner,
        )

    def _parse_capitol_date(self, text: str) -> str:
        """Parse dates like '29 Dec2025' or '14 Apr2025' → YYYY-MM-DD."""
        text = text.replace("\n", " ").strip()
        # Handle "14:05Yesterday" or similar
        if "yesterday" in text.lower() or "today" in text.lower():
            return utcnow().strftime("%Y-%m-%d")

        # Try "29 Dec2025" or "29 Dec 2025"
        m = re.search(r'(\d{1,2})\s*([A-Za-z]{3})\s*(\d{4})', text)
        if m:
            try:
                return datetime.strptime(
                    f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y"
                ).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return text

    # -- House XML fallback --

    def _scrape_house_xml(self) -> List[CongressTrade]:
        """Parse House Clerk XML for PTR filings, then fetch PDFs for details."""
        trades: List[CongressTrade] = []
        year = utcnow().year
        url = f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.xml"

        resp = self.session.get(url, timeout=20)
        if resp.status_code != 200:
            logger.warning(f"House XML returned {resp.status_code}")
            return trades

        text = resp.content.decode("utf-8-sig")
        root = ET.fromstring(text)

        cutoff = utcnow() - timedelta(days=settings.CONGRESS_LOOKBACK_DAYS)
        ptrs = []
        for member in root.findall("Member"):
            filing_type = (member.find("FilingType").text or "").strip()
            if filing_type != "P":
                continue

            filing_date_str = (member.find("FilingDate").text or "").strip()
            try:
                filing_date = datetime.strptime(filing_date_str, "%m/%d/%Y")
                if filing_date < cutoff:
                    continue
            except (ValueError, TypeError):
                pass

            ptrs.append(member)

        logger.info(f"House XML: {len(ptrs)} recent PTR filings")

        for member in ptrs[:30]:  # cap requests
            try:
                member_trades = self._parse_house_xml_member(member, year)
                trades.extend(member_trades)
                time.sleep(1)
            except Exception as e:
                logger.debug(f"House XML member parse error: {e}")

        return trades

    def _parse_house_xml_member(self, member, year: int) -> List[CongressTrade]:
        """Fetch and parse a House PTR PDF for a single member."""
        trades = []
        first = (member.find("First").text or "").strip()
        last = (member.find("Last").text or "").strip()
        politician = f"{first} {last}".strip()
        # Remove honorific prefixes
        politician = re.sub(r'^Hon\.\s*', '', politician)
        filing_date = (member.find("FilingDate").text or "").strip()
        doc_id = (member.find("DocID").text or "").strip()

        if not doc_id:
            return trades

        pdf_url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
        return self._parse_house_pdf(pdf_url, politician, filing_date)

    def _parse_house_pdf(self, url: str, politician: str, filing_date: str) -> List[CongressTrade]:
        """Download and parse a House PTR PDF."""
        trades = []
        try:
            import pdfplumber
        except ImportError:
            logger.debug("pdfplumber not installed, skipping PDF parsing")
            return trades

        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200:
                return trades

            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(resp.content)
                tmp_path = f.name

            try:
                with pdfplumber.open(tmp_path) as pdf:
                    full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            finally:
                os.unlink(tmp_path)

            if not full_text.strip():
                return trades

            # Parse ticker symbols from PDF text
            # Format: "description (TICKER) [ST]" followed by P/S, date, amount
            # e.g.: "SP Netflix, Inc. - Common Stock (NFLX) S 12/12/2025 01/06/2026 $1,001 - $15,000"
            pattern = re.compile(
                r'\(([A-Z]{1,5})\)\s*(?:\[ST\])?\s*'
                r'(P|S|Purchase|Sale)\s+'
                r'(\d{1,2}/\d{1,2}/\d{4})?\s*'
                r'(?:\d{1,2}/\d{1,2}/\d{4})?\s*'
                r'(\$[\d,]+\s*-\s*\$[\d,]+|\$[\d,]+\s*\+)',
            )

            for match in pattern.finditer(full_text):
                ticker = match.group(1)
                tx_type = match.group(2)
                tx_date = match.group(3) or ""
                amount = match.group(4).strip()

                direction = "Purchase" if tx_type in ("P", "Purchase") else "Sale"
                party = _lookup_party(politician)

                # Determine owner from preceding text (SP=Spouse, JT=Joint, DC=Dependent Child)
                start = max(0, match.start() - 5)
                prefix = full_text[start:match.start()].strip()
                if prefix.startswith("SP"):
                    owner = "Spouse"
                elif prefix.startswith("JT"):
                    owner = "Joint"
                elif prefix.startswith("DC"):
                    owner = "Child"
                else:
                    owner = "Self"

                trades.append(CongressTrade(
                    politician=politician,
                    party=party,
                    chamber="House",
                    ticker=ticker,
                    asset_description="",
                    direction=direction,
                    amount_range=amount,
                    transaction_date=tx_date,
                    filing_date=filing_date,
                    owner=owner,
                ))

        except Exception as e:
            logger.debug(f"PDF parse error for {url}: {e}")

        return trades

    # -- Cache --

    def _is_cache_fresh(self) -> bool:
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT fetched_at FROM congress_cache ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if not row:
                    return False
                ttl = timedelta(hours=settings.CONGRESS_CACHE_TTL_HOURS)
                return utcnow() - row[0] < ttl if row[0].tzinfo else utcnow() - row[0] < ttl
        except Exception:
            return False

    def _load_cache(self) -> Optional[List[CongressTrade]]:
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT data FROM congress_cache ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if not row:
                    return None
                return [CongressTrade(**t) for t in row[0].get("trades", [])]
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
            return None

    def _save_cache(self, trades: List[CongressTrade]):
        try:
            data = {
                "trade_count": len(trades),
                "trades": [asdict(t) for t in trades],
            }
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO congress_cache (data) VALUES (%s)",
                    (json.dumps(data),),
                )
                conn.commit()
            logger.info(f"Cached {len(trades)} congress trades")
        except Exception as e:
            logger.warning(f"Failed to cache congress trades: {e}")

    # -- Helpers --

    @staticmethod
    def _extract_ticker_from_issuer(text: str) -> Optional[str]:
        """Extract ticker from Capitol Trades issuer cell, e.g. 'Fluor CorpFLR:US'."""
        if not text:
            return None
        # Try "TICKER:US" format
        m = re.search(r'([A-Z]{1,5}):US', text)
        if m:
            return m.group(1)
        # Try parenthetical
        m = re.search(r'\(([A-Z]{1,5})\)', text)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _extract_ticker(text: str) -> Optional[str]:
        """Extract ticker symbol from text like 'AAPL', '$AAPL', or 'AAPL - Apple Inc'."""
        if not text:
            return None
        text = text.strip().lstrip("$")
        match = re.match(r'^([A-Z]{1,5})\b', text.upper())
        return match.group(1) if match else None

    @staticmethod
    def _extract_ticker_from_desc(desc: str) -> Optional[str]:
        """Extract ticker from asset description like 'Apple Inc (AAPL)' or 'AAPL'."""
        if not desc:
            return None
        # Try parenthetical ticker first
        m = re.search(r'\(([A-Z]{1,5})\)', desc)
        if m:
            return m.group(1)
        # Try leading ticker
        m = re.match(r'^([A-Z]{1,5})\b', desc.strip())
        if m and m.group(1) not in ("THE", "AND", "FOR", "NOT"):
            return m.group(1)
        return None
