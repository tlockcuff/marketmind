"""Bot start/stop/status endpoints."""

from fastapi import APIRouter

from api.bot_manager import get_bot_manager

router = APIRouter()


@router.post("/api/bot/start")
async def bot_start():
    mgr = get_bot_manager()
    mgr.start()
    return {"status": "ok", "running": mgr.is_running()}


@router.post("/api/bot/stop")
async def bot_stop():
    mgr = get_bot_manager()
    mgr.stop()
    return {"status": "ok", "running": False}


@router.get("/api/bot/status")
async def bot_status():
    mgr = get_bot_manager()
    return {
        "running": mgr.is_running(),
        "uptime": mgr.uptime_seconds(),
    }
