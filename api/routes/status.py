from fastapi import APIRouter
from api.data_provider import get_status

router = APIRouter()


@router.get("/api/status")
async def status():
    return get_status()
