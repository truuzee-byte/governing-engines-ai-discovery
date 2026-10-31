from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PendingAction:
    action_id: str
    action_type: str
    awaiting: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)


def create_memory_save_pending_action(memory_text: str) -> PendingAction:
    return PendingAction(
        action_id=f"pa-{uuid4().hex}",
        action_type="SAVE_MEMORY",
        awaiting="STORAGE_SCOPE",
        payload={"memory_text": memory_text},
    )