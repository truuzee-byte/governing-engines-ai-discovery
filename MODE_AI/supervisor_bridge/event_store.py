from __future__ import annotations

import json
from typing import List

from .database import BridgeDatabase
from .models import SupervisorEvent, new_id, utc_now


class EventStore:
    def __init__(self, db: BridgeDatabase) -> None:
        self.db = db

    def append(self, task_id: str, event_type: str, actor: str, **kwargs) -> SupervisorEvent:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS max_seq FROM supervisor_events WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            sequence = int(row["max_seq"]) + 1
            event = SupervisorEvent(
                event_id=new_id("event"), sequence=sequence, task_id=task_id,
                event_type=event_type, actor=actor,
                target=kwargs.get("target"), operation=kwargs.get("operation"),
                status=kwargs.get("status"), message=kwargs.get("message"),
                detail=dict(kwargs.get("detail") or {}),
                evidence_refs=list(kwargs.get("evidence_refs") or []),
                created_at=utc_now(),
            )
            conn.execute(
                """INSERT INTO supervisor_events
                (event_id,task_id,sequence,event_type,actor,target,operation,status,message,detail_json,evidence_refs_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event.event_id, event.task_id, event.sequence, event.event_type, event.actor,
                 event.target, event.operation, event.status, event.message,
                 json.dumps(event.detail), json.dumps(event.evidence_refs), event.created_at),
            )
            conn.execute(
                "UPDATE supervisor_tasks SET latest_event_sequence = ?, updated_at = ? WHERE task_id = ?",
                (sequence, event.created_at, task_id),
            )
        return event

    def list(self, task_id: str, after_sequence: int = 0) -> List[SupervisorEvent]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM supervisor_events WHERE task_id = ? AND sequence > ? ORDER BY sequence ASC",
                (task_id, after_sequence),
            ).fetchall()
        return [
            SupervisorEvent(
                event_id=r["event_id"], sequence=int(r["sequence"]), task_id=r["task_id"],
                event_type=r["event_type"], actor=r["actor"], target=r["target"],
                operation=r["operation"], status=r["status"], message=r["message"],
                detail=json.loads(r["detail_json"]), evidence_refs=json.loads(r["evidence_refs_json"]),
                created_at=r["created_at"],
            ) for r in rows
        ]
