"""WebSocket connection manager with background broadcast."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket

from api.data_provider import get_full_snapshot

logger = logging.getLogger(__name__)

BROADCAST_INTERVAL = 0.5  # seconds


class ConnectionManager:
    def __init__(self):
        self.active: set[WebSocket] = set()
        self._task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)
        logger.info(f"WS connected ({len(self.active)} clients)")

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)
        logger.info(f"WS disconnected ({len(self.active)} clients)")

    async def broadcast(self, data: dict):
        payload = json.dumps(data)
        dead = set()
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self.active -= dead

    async def _broadcast_loop(self):
        while True:
            try:
                if self.active:
                    snapshot = await asyncio.to_thread(get_full_snapshot)
                    await self.broadcast(snapshot)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
            await asyncio.sleep(BROADCAST_INTERVAL)

    def start(self):
        self._task = asyncio.create_task(self._broadcast_loop())

    def stop(self):
        if self._task:
            self._task.cancel()


manager = ConnectionManager()
