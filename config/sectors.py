"""Static sector map for common tickers + fallback."""

MAX_PER_SECTOR = 3

SECTOR_MAP = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology", "GOOG": "Technology",
    "META": "Technology", "AMZN": "Technology", "NVDA": "Technology", "AMD": "Technology",
    "INTC": "Technology", "CRM": "Technology", "ORCL": "Technology", "ADBE": "Technology",
    "CSCO": "Technology", "AVGO": "Technology", "QCOM": "Technology", "TXN": "Technology",
    "MU": "Technology", "MRVL": "Technology", "ANET": "Technology", "SNPS": "Technology",
    "NOW": "Technology", "PANW": "Technology", "CRWD": "Technology", "PLTR": "Technology",
    # Financials
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials", "MS": "Financials",
    "WFC": "Financials", "C": "Financials", "SCHW": "Financials", "BLK": "Financials",
    "V": "Financials", "MA": "Financials", "PYPL": "Financials", "SQ": "Financials",
    # Healthcare
    "JNJ": "Healthcare", "UNH": "Healthcare", "PFE": "Healthcare", "ABBV": "Healthcare",
    "MRK": "Healthcare", "LLY": "Healthcare", "TMO": "Healthcare", "ABT": "Healthcare",
    "MRNA": "Healthcare", "ISRG": "Healthcare",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy",
    "OXY": "Energy", "EOG": "Energy", "MPC": "Energy", "VLO": "Energy",
    # Consumer
    "TSLA": "Consumer", "NKE": "Consumer", "SBUX": "Consumer", "MCD": "Consumer",
    "DIS": "Consumer", "NFLX": "Consumer", "HD": "Consumer", "LOW": "Consumer",
    "COST": "Consumer", "WMT": "Consumer", "TGT": "Consumer",
    # Industrials / Defense
    "BA": "Industrials", "CAT": "Industrials", "HON": "Industrials", "UPS": "Industrials",
    "LMT": "Defense", "RTX": "Defense", "NOC": "Defense", "GD": "Defense",
    # Space
    "RKLB": "Space", "LUNR": "Space", "RDW": "Space", "ASTS": "Space",
    # Nuclear / Uranium
    "CCJ": "Nuclear", "LEU": "Nuclear", "SMR": "Nuclear", "UEC": "Nuclear",
    "NNE": "Nuclear", "OKLO": "Nuclear",
    # Materials
    "MP": "Materials", "LAC": "Materials", "ALB": "Materials", "VALE": "Materials",
}


def get_sector(ticker: str, grok_sector: str = None) -> str:
    """Return sector for ticker. Static map first, then Grok-provided, else Unknown."""
    if ticker in SECTOR_MAP:
        return SECTOR_MAP[ticker]
    if grok_sector:
        return grok_sector
    return "Unknown"
