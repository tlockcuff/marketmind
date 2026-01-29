from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from config import settings

router = APIRouter()


class TargetRequest(BaseModel):
    target: Optional[float] = None


@router.get("/api/target")
async def get_target():
    target = settings.get_daily_target()
    return {"target": target}


@router.post("/api/target")
async def set_target(req: TargetRequest):
    settings.set_daily_target(req.target)
    return {"target": req.target, "status": "ok"}
