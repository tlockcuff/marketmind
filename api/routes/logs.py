from fastapi import APIRouter, Query
from api.data_provider import get_logs

router = APIRouter()


@router.get("/api/logs")
async def logs(n: int = Query(default=100, ge=1, le=1000)):
    return get_logs(n)
