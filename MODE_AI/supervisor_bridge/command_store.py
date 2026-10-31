from __future__ import annotations

from typing import List

from .database import BridgeDatabase
from .models import SupervisorCommand, new_id, utc_now


ALLOWED_COMMANDS = {
    "PAUSE", "CONTINUE", "HALT", "REQUEST_EVIDENCE", "REQUEST_INSPECTION",
    "REQUEST_REPLAN", "REQUEST_STATUS", "REQUEST_SPEC_REVIEW",
}


class CommandStore:
    def __init__(self, db: BridgeDatabase) -> None:
        self.db = db

    def create(self, task_id: str, command: str, reason: str, issued_by: str = "CHATGPT") -> SupervisorCommand:
        command = command.strip().upper()
        if command not in ALLOWED_COMMANDS:
            raise ValueError("invalid supervisor command")
        item = SupervisorCommand(
            command_id=new_id("cmd"), task_id=task_id, command=command,
            reason=reason or command, issued_by=issued_by,
        )
        with self.db.connection() as conn:
            conn.execute(
                "INSERT INTO supervisor_commands VALUES (?,?,?,?,?,?,?,?)",
                (item.command_id, item.task_id, item.command, item.reason, item.issued_by,
                 item.created_at, item.status, item.applied_at),
            )
        return item

    def mark_applied(self, command_id: str) -> None:
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE supervisor_commands SET status='APPLIED', applied_at=? WHERE command_id=?",
                (utc_now(), command_id),
            )
