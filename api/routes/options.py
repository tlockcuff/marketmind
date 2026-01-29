from fastapi import APIRouter
from api.data_provider import get_options

router = APIRouter()


@router.get("/api/options")
async def options():
    return get_options()
