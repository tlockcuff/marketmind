from fastapi import APIRouter, Query
from api.news_provider import fetch_news

router = APIRouter()


@router.get("/api/news")
async def news(sector: str = Query(default=None), limit: int = Query(default=50)):
    return fetch_news(sector=sector, limit=limit)
