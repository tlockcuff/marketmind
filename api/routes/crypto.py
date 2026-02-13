from fastapi import APIRouter
from api.data_provider import get_crypto_positions

router = APIRouter()


@router.get("/api/crypto")
async def crypto():
    return get_crypto_positions()
