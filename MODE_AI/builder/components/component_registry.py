from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


ALL_INITIAL_TOOL_TYPES = [
    "audit_tool",
    "diagnostic_tool",
    "validation_tool",
    "workflow_tool",
    "pipeline_tool",
    "governance_tool",
    "analysis_tool",
    "construction_tool",
]


@dataclass(frozen=True)
class ComponentDefinition:
    component_name: str
    component_type: str
    allowed_tool_types: List[str]
    required_files: List[str]
    required_directories: List[str]
    governance_constraints: List[str]

    def __post_init__(self) -> None:
        _require_non_empty_string(self.component_name, "component_name")
        _require_non_empty_string(self.component_type, "component_type")
        for name in ("allowed_tool_types", "required_files", "required_directories", "governance_constraints"):
            if not isinstance(getattr(self, name), list):
                raise TypeError(f"{name} must be a list")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_name": self.component_name,
            "component_type": self.component_type,
            "allowed_tool_types": list(self.allowed_tool_types),
            "required_files": list(self.required_files),
            "required_directories": list(self.required_directories),
            "governance_constraints": list(self.governance_constraints),
        }


def _require_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _component(name: str, component_type: str, constraints: list[str]) -> ComponentDefinition:
    return ComponentDefinition(
        component_name=name,
        component_type=component_type,
        allowed_tool_types=list(ALL_INITIAL_TOOL_TYPES),
        required_files=[],
        required_directories=[],
        governance_constraints=["component_must_be_registered", *constraints],
    )


REGISTERED_COMPONENTS = {
    "validator": _component("validator", "validation", ["validation_required"]),
    "reporter": _component("reporter", "reporting", ["report_outputs_only"]),
    "receipt_writer": _component("receipt_writer", "receipt", ["receipt_required"]),
    "manifest_validator": _component("manifest_validator", "manifest_validation", ["manifest_validation_required"]),
    "workspace_manager": _component("workspace_manager", "workspace", ["workspace_must_be_governed"]),
    "file_writer": _component("file_writer", "file_generation", ["approved_files_only"]),
    "command_runner": _component("command_runner", "command_execution", ["approved_commands_only"]),
    "repository_inspector": _component("repository_inspector", "repository_observation", ["read_scope_only"]),
    "code_constructor": _component("code_constructor", "code_construction", ["spec_only", "no_direct_execution"]),
    "kernel_gateway": _component("kernel_gateway", "execution_gateway", ["kernel_authorization_required"]),
}


def get_component_definition(component_name: str) -> ComponentDefinition:
    if not isinstance(component_name, str):
        raise TypeError("component_name must be a string")
    normalized = component_name.strip()
    if normalized not in REGISTERED_COMPONENTS:
        raise ValueError("unregistered component")
    return REGISTERED_COMPONENTS[normalized]


def is_registered_component(component_name: str) -> bool:
    return isinstance(component_name, str) and component_name.strip() in REGISTERED_COMPONENTS
