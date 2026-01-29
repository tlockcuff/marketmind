from fastapi import APIRouter
from api.data_provider import get_stats

router = APIRouter()


@router.get("/api/stats")
async def stats():
    return get_stats()
