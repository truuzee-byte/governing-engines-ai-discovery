from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone


class OperatorRequirementDomain(str, Enum):
    GENERAL = "GENERAL"
    HEALTH = "HEALTH"
    FINANCIAL_PLANNING = "FINANCIAL_PLANNING"
    LEGAL_ASSISTANCE = "LEGAL_ASSISTANCE"
    EDUCATION = "EDUCATION"
    PROFESSIONAL = "PROFESSIONAL"
    ENGINEERING = "ENGINEERING"
    ENTERPRISE_WORKFLOW = "ENTERPRISE_WORKFLOW"


class OperatorRequirementStatus(str, Enum):
    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    OPTIONAL = "OPTIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OperatorRequirementSensitivity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class OperatorDataStorageChoice(str, Enum):
    SESSION_ONLY = "SESSION_ONLY"
    PERSISTENT = "PERSISTENT"
    NOT_SELECTED = "NOT_SELECTED"


@dataclass(frozen=True)
class OperatorRequirementDefinition:
    field_name: str
    label: str
    required: bool
    sensitivity: OperatorRequirementSensitivity = OperatorRequirementSensitivity.LOW
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sensitivity"] = self.sensitivity.value
        return data


@dataclass
class OperatorRequirementResult:
    field_name: str
    label: str
    status: OperatorRequirementStatus
    required: bool
    sensitivity: OperatorRequirementSensitivity
    reason: str
    value_present: bool = False
    storage_choice: OperatorDataStorageChoice = OperatorDataStorageChoice.NOT_SELECTED
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["sensitivity"] = self.sensitivity.value
        data["storage_choice"] = self.storage_choice.value
        return data


@dataclass
class OperatorRequirementEvaluation:
    evaluation_id: str
    operator_id: str
    thread_id: str
    input_text: str
    domain: OperatorRequirementDomain
    requirements: list[OperatorRequirementResult]
    created_at: str

    def missing_required_fields(self) -> list[str]:
        return [
            requirement.field_name
            for requirement in self.requirements
            if requirement.required
            and requirement.status == OperatorRequirementStatus.MISSING
        ]

    def satisfied_required_fields(self) -> list[str]:
        return [
            requirement.field_name
            for requirement in self.requirements
            if requirement.required
            and requirement.status == OperatorRequirementStatus.SATISFIED
        ]

    def can_continue(self) -> bool:
        return len(self.missing_required_fields()) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "operator_id": self.operator_id,
            "thread_id": self.thread_id,
            "input_text": self.input_text,
            "domain": self.domain.value,
            "requirements": [
                requirement.to_dict()
                for requirement in self.requirements
            ],
            "missing_required_fields": self.missing_required_fields(),
            "satisfied_required_fields": self.satisfied_required_fields(),
            "can_continue": self.can_continue(),
            "created_at": self.created_at,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_operator_requirement_evaluation_id() -> str:
    return f"ore-{uuid4().hex}"