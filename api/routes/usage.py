from fastapi import APIRouter
from api.data_provider import get_api_usage

router = APIRouter()


@router.get("/api/usage")
async def usage():
    return get_api_usage()
