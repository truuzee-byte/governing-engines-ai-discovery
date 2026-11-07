from __future__ import annotations

from .task_store import TaskStore


class StateService:
    def __init__(self, tasks: TaskStore) -> None:
        self.tasks = tasks

    def get_execution_control(self, task_id: str) -> str:
        state = self.tasks.get(task_id)
        if state.halted:
            return "HALTED"
        if state.paused:
            return "PAUSED"
        return "ACTIVE"
