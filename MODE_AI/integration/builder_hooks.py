from __future__ import annotations

from supervisor_bridge.builder_adapter import BuilderAdapter


def require_builder_active(adapter: BuilderAdapter, task_id: str) -> None:
    control = adapter.check_execution_allowed(task_id)
    if control == "PAUSED":
        raise RuntimeError("SUPERVISOR_PAUSED")
    if control == "HALTED":
        raise RuntimeError("SUPERVISOR_HALTED")


def emit_builder_event(adapter: BuilderAdapter, task_id: str, event_type: str, **detail):
    return adapter.emit(task_id, event_type, **detail)
