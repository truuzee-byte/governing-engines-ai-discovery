from __future__ import annotations

from typing import Any, Dict


class BuilderAdapter:
    def __init__(self, bridge_service: Any) -> None:
        self.bridge = bridge_service

    def check_execution_allowed(self, task_id: str) -> str:
        return self.bridge.state.get_execution_control(task_id)

    def emit(self, task_id: str, event_type: str, **detail: Any):
        return self.bridge.events.append(
            task_id=task_id,
            event_type=event_type,
            actor="BUILDER",
            target=detail.pop("target", None),
            operation=detail.pop("operation", None),
            status=detail.pop("status", None),
            message=detail.pop("message", None),
            detail=detail,
        )
