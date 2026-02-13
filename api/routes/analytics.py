from fastapi import APIRouter, Query
from api.data_provider import get_analytics_data, get_equity_curve_data, get_strategy_breakdown_data, get_trade_analysis_data

router = APIRouter()


@router.get("/api/analytics")
async def analytics(range: str = Query("ALL", regex="^(1W|1M|3M|ALL)$")):
    return get_analytics_data(range)


@router.get("/api/analytics/equity-curve")
async def equity_curve(range: str = Query("ALL", regex="^(1W|1M|3M|ALL)$")):
    """Daily equity + benchmarks comparison."""
    return get_equity_curve_data(range)


@router.get("/api/analytics/strategy-breakdown")
async def strategy_breakdown(range: str = Query("ALL", regex="^(1W|1M|3M|ALL)$")):
    """Per-strategy performance stats."""
    return get_strategy_breakdown_data(range)


@router.get("/api/analytics/trade-analysis")
async def trade_analysis(range: str = Query("ALL", regex="^(1W|1M|3M|ALL)$")):
    """Hold duration, best/worst trades, recent performance."""
    return get_trade_analysis_data(range)
