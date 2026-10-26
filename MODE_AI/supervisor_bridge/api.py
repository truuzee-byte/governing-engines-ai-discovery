from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .auth import build_auth_dependency
from .config import BridgeConfig
from .errors import TaskNotFound
from .service import SupervisorBridgeService
from .websocket_manager import WebSocketManager
from .repository_reader import RepositoryAccessError, RepositoryReader

class MessageBody(BaseModel):
    message: str
    message_type: str = "MESSAGE"


class CommandBody(BaseModel):
    reason: str = ""


def create_app(service: SupervisorBridgeService | None = None) -> FastAPI:
    bridge = service or SupervisorBridgeService()
    config = bridge.config
    require_auth = build_auth_dependency(config)
    ws_manager = WebSocketManager()
    app = FastAPI(title="MODE Supervisor Bridge", version="1.0")
    from pathlib import Path
    repository = RepositoryReader(Path(__file__).resolve().parents[1])
    
    @app.get("/health")
    async def health():
        return {"ok": True, "service": "mode_supervisor_bridge"}

    @app.get("/supervisor/tasks/{task_id}", dependencies=[Depends(require_auth)])
    async def get_task(task_id: str):
        try:
            return bridge.tasks.get(task_id).to_dict()
        except TaskNotFound:
            raise HTTPException(status_code=404, detail="task not found")

    @app.get("/supervisor/tasks/{task_id}/events", dependencies=[Depends(require_auth)])
    async def get_events(task_id: str, after_sequence: int = 0):
        return [e.to_dict() for e in bridge.events.list(task_id, after_sequence)]

    @app.get("/supervisor/tasks/{task_id}/responses", dependencies=[Depends(require_auth)])
    async def get_responses(task_id: str):
        return [r.to_dict() for r in bridge.messages.responses(task_id)]

    @app.post("/supervisor/tasks/{task_id}/messages", dependencies=[Depends(require_auth)])
    async def send_message(task_id: str, body: MessageBody):
        return bridge.send_message(task_id, body.message, body.message_type).to_dict()

    def add_command_route(path: str, command: str):
        async def handler(task_id: str, body: CommandBody):
            return bridge.supervisor.apply(task_id, command, body.reason).to_dict()
        app.post(path, dependencies=[Depends(require_auth)])(handler)

    add_command_route("/supervisor/tasks/{task_id}/pause", "PAUSE")
    add_command_route("/supervisor/tasks/{task_id}/continue", "CONTINUE")
    add_command_route("/supervisor/tasks/{task_id}/halt", "HALT")
    add_command_route("/supervisor/tasks/{task_id}/request-evidence", "REQUEST_EVIDENCE")
    add_command_route("/supervisor/tasks/{task_id}/request-inspection", "REQUEST_INSPECTION")
    add_command_route("/supervisor/tasks/{task_id}/request-replan", "REQUEST_REPLAN")

    @app.websocket("/supervisor/tasks/{task_id}/stream")
    async def stream(task_id: str, websocket: WebSocket):
        token = websocket.query_params.get("token", "")
        if token != config.require_token():
            await websocket.close(code=4403)
            return
        await ws_manager.connect(task_id, websocket)
        last_seq = int(websocket.query_params.get("after_sequence", "0"))
        try:
            while True:
                events = bridge.events.list(task_id, last_seq)
                for event in events:
                    await websocket.send_json({"message_kind": "EXECUTION_EVENT", "payload": event.to_dict()})
                    last_seq = event.sequence
                await websocket.send_json({"message_kind": "HEARTBEAT", "task_id": task_id, "sequence": last_seq})
                import asyncio
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            await ws_manager.disconnect(task_id, websocket)
    # ---------------------------------------------------------
    # Read-only repository inspection surface
    # Root is scoped to this publication checkout, not an operational installation.
    # ---------------------------------------------------------

    @app.get(
        "/repository/list",
        dependencies=[Depends(require_auth)],
    )
    async def repository_list(path: str = ""):
        try:
            return repository.list_directory(path)
        except RepositoryAccessError as exc:
            raise HTTPException(status_code=403, detail=str(exc))

    @app.get(
        "/repository/read",
        dependencies=[Depends(require_auth)],
    )
    async def repository_read(path: str):
        try:
            return repository.read_file(path)
        except RepositoryAccessError as exc:
            raise HTTPException(status_code=403, detail=str(exc))

    @app.get(
        "/repository/search",
        dependencies=[Depends(require_auth)],
    )
    async def repository_search(
        query: str,
        path: str = "",
    ):
        try:
            return repository.search(
                query,
                relative_path=path,
            )
        except RepositoryAccessError as exc:
            raise HTTPException(status_code=403, detail=str(exc))

    @app.get(
        "/repository/status",
        dependencies=[Depends(require_auth)],
    )
    async def repository_status():
        return repository.git_status()

    @app.get(
        "/repository/diff",
        dependencies=[Depends(require_auth)],
    )
    async def repository_diff():
        return repository.git_diff()
    app.state.bridge = bridge
    return app


app = create_app()
