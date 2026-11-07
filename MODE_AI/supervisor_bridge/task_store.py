from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Optional

from .database import BridgeDatabase
from .models import SupervisorTaskState, utc_now
from .errors import TaskNotFound


class TaskStore:
    def __init__(self, db: BridgeDatabase) -> None:
        self.db = db

    def upsert(self, state: SupervisorTaskState) -> None:
        payload = state.to_dict()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO supervisor_tasks (
                    task_id, interaction_id, session_id, trace_reference,
                    current_stage, status, active_spec_id, active_spec_hash,
                    mode_state, builder_state, current_component,
                    current_operation, last_operation_result, validation_state,
                    paused, halted, failure_code, failure_detail_json,
                    latest_event_sequence, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(task_id) DO UPDATE SET
                    interaction_id=excluded.interaction_id,
                    session_id=excluded.session_id,
                    trace_reference=excluded.trace_reference,
                    current_stage=excluded.current_stage,
                    status=excluded.status,
                    active_spec_id=excluded.active_spec_id,
                    active_spec_hash=excluded.active_spec_hash,
                    mode_state=excluded.mode_state,
                    builder_state=excluded.builder_state,
                    current_component=excluded.current_component,
                    current_operation=excluded.current_operation,
                    last_operation_result=excluded.last_operation_result,
                    validation_state=excluded.validation_state,
                    paused=excluded.paused,
                    halted=excluded.halted,
                    failure_code=excluded.failure_code,
                    failure_detail_json=excluded.failure_detail_json,
                    latest_event_sequence=excluded.latest_event_sequence,
                    updated_at=excluded.updated_at
                """,
                (
                    payload["task_id"], payload["interaction_id"], payload["session_id"],
                    payload["trace_reference"], payload["current_stage"], payload["status"],
                    payload["active_spec_id"], payload["active_spec_hash"], payload["mode_state"],
                    payload["builder_state"], payload["current_component"], payload["current_operation"],
                    payload["last_operation_result"], payload["validation_state"], int(payload["paused"]),
                    int(payload["halted"]), payload["failure_code"], json.dumps(payload["failure_detail"]),
                    payload["latest_event_sequence"], payload["updated_at"],
                ),
            )

    def get(self, task_id: str) -> SupervisorTaskState:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM supervisor_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        if row is None:
            raise TaskNotFound(task_id)
        return SupervisorTaskState(
            task_id=row["task_id"], interaction_id=row["interaction_id"],
            session_id=row["session_id"], trace_reference=row["trace_reference"],
            current_stage=row["current_stage"], status=row["status"],
            active_spec_id=row["active_spec_id"], active_spec_hash=row["active_spec_hash"],
            mode_state=row["mode_state"], builder_state=row["builder_state"],
            current_component=row["current_component"], current_operation=row["current_operation"],
            last_operation_result=row["last_operation_result"], validation_state=row["validation_state"],
            paused=bool(row["paused"]), halted=bool(row["halted"]),
            failure_code=row["failure_code"],
            failure_detail=json.loads(row["failure_detail_json"] or "null"),
            latest_event_sequence=int(row["latest_event_sequence"]), updated_at=row["updated_at"],
        )

    def patch(self, task_id: str, **changes: Any) -> SupervisorTaskState:
        state = self.get(task_id)
        allowed = set(state.to_dict()) - {"task_id"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unknown task fields: {sorted(unknown)}")
        next_state = replace(state, **changes, updated_at=utc_now())
        self.upsert(next_state)
        return next_state
