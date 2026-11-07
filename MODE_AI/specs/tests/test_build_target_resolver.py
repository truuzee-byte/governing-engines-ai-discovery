from __future__ import annotations

import copy

import pytest

from specs.build_target_resolver import (
    is_supported_tool_type,
    resolve_build_target,
    validate_build_target,
)
from specs.spec_engine import create_specification_object


def test_valid_buildspec_resolves_target() -> None:
    spec = _valid_specification_object()

    target = resolve_build_target(spec)

    assert target["target_name"] == "Diagnostic Tool"
    assert target["tool_type"] == "diagnostic_tool"


def test_return_shape_contains_required_fields() -> None:
    spec = _valid_specification_object()

    target = resolve_build_target(spec)

    assert set(target.keys()) == {
        "target_name",
        "tool_type",
        "system_name",
        "runtime_target",
        "spec_id",
        "spec_reference",
        "authority_state",
    }


def test_unsupported_tool_type_fails_validation() -> None:
    spec = _valid_specification_object()
    spec["structure"]["tool_type"] = "unsupported_tool"

    result = validate_build_target(spec)

    assert result.failed() is True
    assert result.failure_reason == "unsupported tool_type"


def test_missing_system_name_fails() -> None:
    spec = _valid_specification_object()
    spec["structure"].pop("system_name")

    result = validate_build_target(spec)

    assert result.failed() is True
    assert result.failure_reason == "missing system_name"


def test_invalid_system_name_fails() -> None:
    spec = _valid_specification_object()
    spec["structure"]["system_name"] = ""

    result = validate_build_target(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid system_name"


def test_missing_tool_type_fails() -> None:
    spec = _valid_specification_object()
    spec["structure"].pop("tool_type")

    result = validate_build_target(spec)

    assert result.failed() is True
    assert result.failure_reason == "missing tool_type"


def test_invalid_tool_type_fails() -> None:
    spec = _valid_specification_object()
    spec["structure"]["tool_type"] = ""

    result = validate_build_target(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid tool_type"


def test_missing_spec_id_fails() -> None:
    spec = _valid_specification_object()
    spec.pop("spec_id")

    result = validate_build_target(spec)

    assert result.failed() is True
    assert result.failure_reason == "missing spec_id"


def test_invalid_spec_id_fails() -> None:
    spec = _valid_specification_object()
    spec["spec_id"] = ""

    result = validate_build_target(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid spec_id"


def test_missing_authority_state_fails() -> None:
    spec = _valid_specification_object()
    spec.pop("authority_state")

    result = validate_build_target(spec)

    assert result.failed() is True
    assert result.failure_reason == "missing authority_state"


def test_invalid_authority_state_fails() -> None:
    spec = _valid_specification_object()
    spec["authority_state"] = ""

    result = validate_build_target(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid authority_state"


def test_raw_conversation_string_input_rejected() -> None:
    result = validate_build_target("build a diagnostic tool")

    assert result.failed() is True
    assert result.failure_reason == "specification_object must be a dictionary"


def test_structure_only_input_rejected() -> None:
    spec = _valid_specification_object()

    result = validate_build_target(spec["structure"])

    assert result.failed() is True
    assert result.failure_reason == "invalid object_type"


def test_resolve_build_target_raises_value_error_when_validation_fails() -> None:
    spec = _valid_specification_object()
    spec["structure"]["tool_type"] = "unsupported_tool"

    with pytest.raises(ValueError):
        resolve_build_target(spec)


def test_is_supported_tool_type_returns_true_for_supported_tools() -> None:
    for tool_type in (
        "audit_tool",
        "diagnostic_tool",
        "validation_tool",
        "workflow_tool",
        "pipeline_tool",
        "governance_tool",
        "analysis_tool",
    ):
        assert is_supported_tool_type(tool_type) is True


def test_is_supported_tool_type_returns_false_for_unsupported_tools() -> None:
    assert is_supported_tool_type("unsupported_tool") is False


def _valid_interpreted_build_request() -> dict:
    return {
        "request_id": "REQ-001",
        "authority_state": "handoff_approved",
        "validation_state": "valid",
        "readiness_state": "ready_for_build",
        "save_ready_state": True,
        "clarification_required": False,
        "system_name": "Diagnostic Tool",
        "system_purpose": "Validate runtime construction behavior",
        "tool_type": "diagnostic_tool",
        "construction_scope": ["create_files", "validate_outputs"],
        "approved_components": ["validator", "reporter"],
        "governance_constraints": ["no_raw_conversation", "no_unapproved_files"],
        "execution_authority": "operator_confirmed",
        "receipt_requirements": ["build_receipt"],
        "runtime_target": None,
        "source_trace_reference": "trace_source_REQ-001",
    }


def _valid_specification_object() -> dict:
    return copy.deepcopy(create_specification_object(_valid_interpreted_build_request()))
