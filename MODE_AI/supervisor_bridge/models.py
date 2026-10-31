from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


@dataclass(frozen=True)
class SupervisorTaskState:
    task_id: str
    interaction_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_reference: Optional[str] = None
    current_stage: str = "IDLE"
    status: str = "ACTIVE"
    active_spec_id: Optional[str] = None
    active_spec_hash: Optional[str] = None
    mode_state: str = "IDLE"
    builder_state: Optional[str] = None
    current_component: Optional[str] = None
    current_operation: Optional[str] = None
    last_operation_result: Optional[str] = None
    validation_state: Optional[str] = None
    paused: bool = False
    halted: bool = False
    failure_code: Optional[str] = None
    failure_detail: Optional[Dict[str, Any]] = None
    latest_event_sequence: int = 0
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SupervisorEvent:
    event_id: str
    sequence: int
    task_id: str
    event_type: str
    actor: str
    target: Optional[str] = None
    operation: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SupervisorCommand:
    command_id: str
    task_id: str
    command: str
    reason: str
    issued_by: str = "CHATGPT"
    created_at: str = field(default_factory=utc_now)
    status: str = "RECEIVED"
    applied_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SupervisorMessage:
    message_id: str
    task_id: str
    sender: str
    message_type: str
    message: str
    related_event_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    delivery_state: str = "PENDING"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModeResponse:
    response_id: str
    task_id: str
    response_type: str
    message: str
    current_state: str
    related_event_ids: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    requested_action: Optional[str] = None
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
