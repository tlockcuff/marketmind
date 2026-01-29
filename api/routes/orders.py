from fastapi import APIRouter
from api.data_provider import get_orders

router = APIRouter()


@router.get("/api/orders")
async def orders():
    return get_orders()
