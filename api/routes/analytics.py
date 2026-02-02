from fastapi import APIRouter, Query
from api.data_provider import get_analytics_data

router = APIRouter()


@router.get("/api/analytics")
async def analytics(range: str = Query("ALL", regex="^(1W|1M|3M|ALL)$")):
    return get_analytics_data(range)
