from fastapi import APIRouter
from api.data_provider import get_account

router = APIRouter()


@router.get("/api/account")
async def account():
    return get_account()
