from __future__ import annotations

import json
from typing import List

from .database import BridgeDatabase
from .models import ModeResponse, SupervisorMessage, new_id, utc_now


class MessageStore:
    def __init__(self, db: BridgeDatabase) -> None:
        self.db = db

    def create_message(self, task_id: str, message: str, sender: str = "CHATGPT", message_type: str = "MESSAGE") -> SupervisorMessage:
        if not message.strip():
            raise ValueError("message must not be empty")
        item = SupervisorMessage(
            message_id=new_id("msg"), task_id=task_id, sender=sender,
            message_type=message_type, message=message,
        )
        with self.db.connection() as conn:
            conn.execute(
                "INSERT INTO supervisor_messages VALUES (?,?,?,?,?,?,?,?)",
                (item.message_id, item.task_id, item.sender, item.message_type, item.message,
                 json.dumps(item.related_event_ids), item.created_at, item.delivery_state),
            )
        return item

    def pending(self, task_id: str, limit: int = 10) -> List[SupervisorMessage]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM supervisor_messages WHERE task_id=? AND delivery_state='PENDING' ORDER BY created_at ASC LIMIT ?",
                (task_id, limit),
            ).fetchall()
        return [SupervisorMessage(
            message_id=r["message_id"], task_id=r["task_id"], sender=r["sender"],
            message_type=r["message_type"], message=r["message"],
            related_event_ids=json.loads(r["related_event_ids_json"]), created_at=r["created_at"],
            delivery_state=r["delivery_state"],
        ) for r in rows]

    def mark_delivered(self, message_id: str) -> None:
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE supervisor_messages SET delivery_state='DELIVERED' WHERE message_id=?",
                (message_id,),
            )

    def record_response(self, task_id: str, message: str, current_state: str, response_type: str = "ANSWER", requested_action: str | None = None) -> ModeResponse:
        item = ModeResponse(
            response_id=new_id("resp"), task_id=task_id, response_type=response_type,
            message=message, current_state=current_state, requested_action=requested_action,
        )
        with self.db.connection() as conn:
            conn.execute(
                "INSERT INTO mode_responses VALUES (?,?,?,?,?,?,?,?,?)",
                (item.response_id, item.task_id, item.response_type, item.message, item.current_state,
                 json.dumps(item.related_event_ids), json.dumps(item.evidence_refs), item.requested_action, item.created_at),
            )
        return item

    def responses(self, task_id: str) -> List[ModeResponse]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM mode_responses WHERE task_id=? ORDER BY created_at ASC", (task_id,)
            ).fetchall()
        return [ModeResponse(
            response_id=r["response_id"], task_id=r["task_id"], response_type=r["response_type"],
            message=r["message"], current_state=r["current_state"],
            related_event_ids=json.loads(r["related_event_ids_json"]),
            evidence_refs=json.loads(r["evidence_refs_json"]), requested_action=r["requested_action"],
            created_at=r["created_at"],
        ) for r in rows]
