from fastapi import APIRouter
from api.data_provider import get_trade_history_data

router = APIRouter()


@router.get("/api/history")
async def history():
    return get_trade_history_data()
