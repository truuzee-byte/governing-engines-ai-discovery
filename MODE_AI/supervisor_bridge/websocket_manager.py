from __future__ import annotations

import asyncio
from typing import Dict, Set

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(task_id, set()).add(websocket)

    async def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.get(task_id, set()).discard(websocket)

    async def publish(self, task_id: str, payload: dict) -> None:
        async with self._lock:
            sockets = list(self._connections.get(task_id, set()))
        dead = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(task_id, ws)
