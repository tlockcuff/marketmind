# Congressional Stock Trading Pipeline

Scrapes STOCK Act PTR (Periodic Transaction Report) filings from both chambers of Congress and injects them as context into Grok's signal generation prompt.

## How It Works

```
Senate efdsearch + House disclosures-clerk
  → Parse PTR filings (HTML + PDF)
  → Cache to logs/congress_trades.json (6hr TTL)
  → Format top 20 trades by dollar amount
  → Append to Grok market_context
  → Grok factors politician trades into signal rationale
```

## Settings

| Setting | Default | Env Override | Purpose |
|---------|---------|-------------|---------|
| `CONGRESS_ENABLED` | `True` | `CONGRESS_ENABLED=false` | Kill switch |
| `CONGRESS_CACHE_TTL_HOURS` | `6` | — | Cache freshness window |
| `CONGRESS_LOOKBACK_DAYS` | `30` | — | How far back to scrape |

## Data Sources

### Senate
- **URL:** `efdsearch.senate.gov/search/`
- Accepts disclaimer via POST, then searches for PTR filings
- Parses JSON listing → fetches each detail page → extracts transaction table rows
- Fields: senator name, ticker, direction, amount range, date, owner

### House
- **URL:** `disclosures-clerk.house.gov/FinancialDisclosure`
- Extracts ASP.NET form tokens, POSTs search for PTR filings
- HTML reports parsed directly; PDF reports parsed via `pdfplumber`
- Falls back to JSON endpoint if HTML search fails

## Cache

Stored at `logs/congress_trades.json`:
```json
{
  "cached_at": "2025-01-28T14:30:00",
  "trade_count": 42,
  "trades": [
    {
      "politician": "Tommy Tuberville",
      "party": "R",
      "chamber": "Senate",
      "ticker": "NVDA",
      "direction": "Purchase",
      "amount_range": "$50,001 - $100,000",
      "transaction_date": "01/15/2025",
      "filing_date": "01/20/2025",
      "owner": "Self"
    }
  ]
}
```

## Context Format

Injected into Grok's prompt as:
```
RECENT CONGRESSIONAL TRADES (last 30 days):
- Sen. Tommy Tuberville (R) BOUGHT $50,001 - $100,000 NVDA on 01/15 (filed 01/20)
- Rep. Nancy Pelosi (D) SOLD $1,000,001 - $5,000,000 AAPL on 01/10 (filed 01/18)
Notable clusters: NVDA (3 buys), AAPL (2 sales)
```

Top 20 trades by dollar amount. Capped at ~500 tokens. Includes cluster detection for multiple members trading the same ticker.

## Grok Integration

System prompt tells Grok:
- Treat congressional trades as **directional sentiment, not timing signals** (filings delayed up to 45 days)
- Multiple members buying same stock = stronger signal
- Note which politician(s) influenced the recommendation in the rationale field

## Party Lookup

Hardcoded dict of ~100 most-active traders (name → R/D/I). Unknown politicians tagged as `(?)` and logged at DEBUG level.

## Dependencies

- `beautifulsoup4` — HTML parsing for both chambers
- `pdfplumber` — House PDF report extraction
- `requests` — already present

## Tests

```bash
pytest tests/test_congress_client.py -v
```

Covers: HTML parsing (Senate + House), cache TTL logic, context string formatting, non-stock filtering, amount sorting, cluster summaries, disabled state.

## Limitations

- STOCK Act filings are delayed up to 45 days — stale by nature
- House PDFs have inconsistent formatting; regex extraction is best-effort
- Party dict requires manual maintenance for new members
- Senate site requires disclaimer acceptance per session
- Rate-limited to 1 request/sec to avoid being blocked
