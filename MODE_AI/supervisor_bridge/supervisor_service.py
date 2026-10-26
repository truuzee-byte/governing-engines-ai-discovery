from __future__ import annotations

from .command_store import CommandStore
from .event_store import EventStore
from .task_store import TaskStore


class SupervisorService:
    def __init__(self, tasks: TaskStore, commands: CommandStore, events: EventStore) -> None:
        self.tasks = tasks
        self.commands = commands
        self.events = events

    def apply(self, task_id: str, command: str, reason: str, issued_by: str = "CHATGPT"):
        item = self.commands.create(task_id, command, reason, issued_by)
        if item.command == "PAUSE":
            with self.tasks.db.connection() as conn:
                conn.execute("UPDATE supervisor_tasks SET paused=1, status=CASE WHEN halted=1 THEN 'HALTED' ELSE 'PAUSED' END WHERE task_id=?", (task_id,))
            event_type = "SUPERVISOR_PAUSED"
        elif item.command == "CONTINUE":
            with self.tasks.db.connection() as conn:
                conn.execute("UPDATE supervisor_tasks SET paused=0, status=CASE WHEN halted=1 THEN 'HALTED' ELSE 'ACTIVE' END WHERE task_id=?", (task_id,))
            event_type = "SUPERVISOR_CONTINUED"
        elif item.command == "HALT":
            with self.tasks.db.connection() as conn:
                conn.execute("UPDATE supervisor_tasks SET halted=1, paused=0, status='HALTED' WHERE task_id=?", (task_id,))
            event_type = "SUPERVISOR_HALTED"
        else:
            event_type = item.command
        self.commands.mark_applied(item.command_id)
        self.events.append(task_id, event_type, actor="SUPERVISOR", message=reason)
        return item
