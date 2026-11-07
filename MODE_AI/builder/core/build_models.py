from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


ALLOWED_STATUS_VALUES = {
    "PASS",
    "FAIL",
    "BLOCKED",
    "UNPROVEN",
    "HALTED",
}


@dataclass(frozen=True)
class BuildPlan:
    build_id: str
    spec_id: str
    snapshot_hash: str
    target_name: str
    tool_type: str
    approved_components: List[str]
    required_files: List[str]
    required_directories: List[str]
    required_outputs: List[str]
    governance_constraints: List[str]
    receipt_requirements: List[str]
    repository_target: str = ""
    authorized_read_scope: List[str] = field(default_factory=list)
    authorized_write_scope: List[str] = field(default_factory=list)
    authorized_create_scope: List[str] = field(default_factory=list)
    authorized_delete_scope: List[str] = field(default_factory=list)
    approved_commands: List[List[str]] = field(default_factory=list)
    validation_commands: List[List[str]] = field(default_factory=list)
    validation_requirements: List[str] = field(default_factory=list)
    evidence_requirements: List[str] = field(default_factory=list)
    completion_requirements: List[str] = field(default_factory=list)
    approved_files: Dict[str, str] = field(default_factory=dict)
    existing_files: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.build_id, "build_id")
        _require_non_empty_string(self.spec_id, "spec_id")
        _require_non_empty_string(self.snapshot_hash, "snapshot_hash")
        _require_non_empty_string(self.target_name, "target_name")
        _require_non_empty_string(self.tool_type, "tool_type")
        for name in (
            "approved_components", "required_files", "required_directories",
            "required_outputs", "governance_constraints", "receipt_requirements",
            "authorized_read_scope", "authorized_write_scope", "authorized_create_scope",
            "authorized_delete_scope", "approved_commands", "validation_commands",
            "validation_requirements", "evidence_requirements", "completion_requirements",
            "existing_files",
        ):
            _require_list(getattr(self, name), name)
        if not isinstance(self.approved_files, dict):
            raise TypeError("approved_files must be a dictionary")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "build_id": self.build_id,
            "spec_id": self.spec_id,
            "snapshot_hash": self.snapshot_hash,
            "target_name": self.target_name,
            "tool_type": self.tool_type,
            "approved_components": list(self.approved_components),
            "required_files": list(self.required_files),
            "required_directories": list(self.required_directories),
            "required_outputs": list(self.required_outputs),
            "governance_constraints": list(self.governance_constraints),
            "receipt_requirements": list(self.receipt_requirements),
            "repository_target": self.repository_target,
            "authorized_read_scope": list(self.authorized_read_scope),
            "authorized_write_scope": list(self.authorized_write_scope),
            "authorized_create_scope": list(self.authorized_create_scope),
            "authorized_delete_scope": list(self.authorized_delete_scope),
            "approved_commands": [list(v) for v in self.approved_commands],
            "validation_commands": [list(v) for v in self.validation_commands],
            "validation_requirements": list(self.validation_requirements),
            "evidence_requirements": list(self.evidence_requirements),
            "completion_requirements": list(self.completion_requirements),
            "approved_files": dict(self.approved_files),
            "existing_files": list(self.existing_files),
        }


@dataclass(frozen=True)
class BuilderOutputObject:
    build_id: str
    spec_id: str
    artifact_root: str
    files_written: List[str]
    directories_created: List[str]
    validation_status: str
    receipt_path: str
    command_results: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    evidence_references: List[str] = field(default_factory=list)
    blocked_conditions: List[str] = field(default_factory=list)
    changeset_reference: str = ""

    def __post_init__(self) -> None:
        _require_non_empty_string(self.build_id, "build_id")
        _require_non_empty_string(self.spec_id, "spec_id")
        _require_non_empty_string(self.artifact_root, "artifact_root")
        _require_list(self.files_written, "files_written")
        _require_list(self.directories_created, "directories_created")
        _require_status(self.validation_status, "validation_status")
        _require_non_empty_string(self.receipt_path, "receipt_path")


@dataclass(frozen=True)
class BuildManifest:
    build_id: str
    spec_id: str
    artifact_root: str
    required_files: List[str]
    required_directories: List[str]
    required_outputs: List[str]
    actual_files: List[str]
    actual_directories: List[str]
    command_results: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.build_id, "build_id")
        _require_non_empty_string(self.spec_id, "spec_id")
        _require_non_empty_string(self.artifact_root, "artifact_root")
        for name in (
            "required_files", "required_directories", "required_outputs",
            "actual_files", "actual_directories", "command_results", "validation_results",
        ):
            _require_list(getattr(self, name), name)


@dataclass(frozen=True)
class BuildReceipt:
    intent_id: str
    build_id: str
    snapshot_hash: str
    stages_checked: List[str]
    drift_detected: bool
    final_status: str
    files_written: List[str] = field(default_factory=list)
    directories_created: List[str] = field(default_factory=list)
    commands_executed: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    evidence_references: List[str] = field(default_factory=list)
    blocked_conditions: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_non_empty_string(self.intent_id, "intent_id")
        _require_non_empty_string(self.build_id, "build_id")
        _require_non_empty_string(self.snapshot_hash, "snapshot_hash")
        _require_list(self.stages_checked, "stages_checked")
        if not isinstance(self.drift_detected, bool):
            raise TypeError("drift_detected must be bool")
        _require_status(self.final_status, "final_status")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "build_id": self.build_id,
            "snapshot_hash": self.snapshot_hash,
            "stages_checked": list(self.stages_checked),
            "drift_detected": self.drift_detected,
            "final_status": self.final_status,
            "files_written": list(self.files_written),
            "directories_created": list(self.directories_created),
            "commands_executed": list(self.commands_executed),
            "validation_results": list(self.validation_results),
            "evidence_references": list(self.evidence_references),
            "blocked_conditions": list(self.blocked_conditions),
        }


def _require_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_list(value: Any, field_name: str) -> None:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list")


def _require_status(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if value.strip().upper() not in ALLOWED_STATUS_VALUES:
        raise ValueError(f"{field_name} must be one of {sorted(ALLOWED_STATUS_VALUES)}")
