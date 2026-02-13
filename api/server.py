"""FastAPI app for the day-trading dashboard."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.ws_manager import manager
from api.routes.account import router as account_router
from api.routes.positions import router as positions_router
from api.routes.orders import router as orders_router
from api.routes.options import router as options_router
from api.routes.config import router as config_router
from api.routes.stats import router as stats_router
from api.routes.usage import router as usage_router
from api.routes.logs import router as logs_router
from api.routes.status import router as status_router
from api.routes.history import router as history_router
from api.routes.target import router as target_router
from api.routes.news import router as news_router
from api.routes.reset import router as reset_router
from api.routes.keys import router as keys_router
from api.routes.bot import router as bot_router
from api.routes.analytics import router as analytics_router
from api.routes.crypto import router as crypto_router
from config.logging_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.db import init_db
    init_db()
    manager.start()
    yield
    manager.stop()
    from api.bot_manager import get_bot_manager
    get_bot_manager().stop()


app = FastAPI(title="Day Trading Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(account_router)
app.include_router(positions_router)
app.include_router(orders_router)
app.include_router(options_router)
app.include_router(config_router)
app.include_router(stats_router)
app.include_router(usage_router)
app.include_router(logs_router)
app.include_router(status_router)
app.include_router(history_router)
app.include_router(target_router)
app.include_router(news_router)
app.include_router(reset_router)
app.include_router(keys_router)
app.include_router(bot_router)
app.include_router(analytics_router)
app.include_router(crypto_router)


@app.get("/api/health")
async def health():
    try:
        from src.db import get_db
        with get_db() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {"status": status, "db": db_ok}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(ws)
