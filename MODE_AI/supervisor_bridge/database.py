from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Iterator
from contextlib import contextmanager
from uuid import uuid4


class BridgeDatabase:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def initialize(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        schema = schema_path.read_text(encoding="utf-8")
        with self.connection() as conn:
            conn.executescript(schema)
            conn.execute("""CREATE TABLE IF NOT EXISTS supervisor_message_claims (
                message_id TEXT PRIMARY KEY, owner_token TEXT NOT NULL,
                claimed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                failure_detail TEXT)""")

    def claim_message(self, task_id: str):
        """Serialize selection and ownership across independent connections/processes."""
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            task = conn.execute("SELECT paused, halted FROM supervisor_tasks WHERE task_id=?", (task_id,)).fetchone()
            if task is None or task["paused"] or task["halted"]:
                return None
            row = conn.execute("""SELECT * FROM supervisor_messages
                WHERE task_id=? AND delivery_state='PENDING'
                ORDER BY created_at, message_id LIMIT 1""", (task_id,)).fetchone()
            if row is None:
                return None
            token = uuid4().hex
            conn.execute("INSERT INTO supervisor_message_claims(message_id, owner_token) VALUES (?,?)",
                         (row["message_id"], token))
            conn.execute("UPDATE supervisor_messages SET delivery_state='CLAIMED' WHERE message_id=? AND delivery_state='PENDING'",
                         (row["message_id"],))
            return {**dict(row), "owner_token": token}

    def finish_message(self, message_id, owner_token, *, failure=None):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            result = conn.execute("""UPDATE supervisor_messages SET delivery_state=?
                WHERE message_id=? AND delivery_state='CLAIMED'
                AND EXISTS (SELECT 1 FROM supervisor_message_claims
                            WHERE message_id=? AND owner_token=?)""",
                ("FAILED" if failure is not None else "DELIVERED", message_id, message_id, owner_token))
            if result.rowcount != 1:
                raise ValueError("message claim ownership lost or already finalized")
            conn.execute("UPDATE supervisor_message_claims SET failure_detail=? WHERE message_id=? AND owner_token=?",
                         (failure, message_id, owner_token))

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
