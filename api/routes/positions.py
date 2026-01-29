from fastapi import APIRouter
from api.data_provider import get_positions

router = APIRouter()


@router.get("/api/positions")
async def positions():
    return get_positions()
