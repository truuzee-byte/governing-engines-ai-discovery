from __future__ import annotations

import copy

from specs.spec_engine import create_specification_object
from specs.spec_validator import (
    is_builder_eligible,
    validate_builder_eligibility,
    validate_specification_object,
)


def test_valid_specification_object_passes_validate_specification_object() -> None:
    spec = _valid_specification_object()

    result = validate_specification_object(spec)

    assert result.passed() is True


def test_valid_buildspec_passes_validate_builder_eligibility() -> None:
    spec = _valid_specification_object()

    result = validate_builder_eligibility(spec)

    assert result.passed() is True


def test_wrong_object_type_fails() -> None:
    spec = _valid_specification_object()
    spec["object_type"] = "WrongObject"

    result = validate_specification_object(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid object_type"


def test_unsupported_spec_class_fails() -> None:
    spec = _valid_specification_object()
    spec["spec_class"] = "UnsupportedSpec"

    result = validate_specification_object(spec)

    assert result.failed() is True
    assert result.failure_reason == "unsupported spec_class"


def test_missing_required_specification_object_field_fails() -> None:
    spec = _valid_specification_object()
    spec.pop("spec_id")

    result = validate_specification_object(spec)

    assert result.failed() is True
    assert result.failure_reason == "missing required SpecificationObject field"
    assert result.failing_field == "spec_id"


def test_invalid_authority_state_fails() -> None:
    spec = _valid_specification_object()
    spec["authority_state"] = "invalid_authority"

    result = validate_specification_object(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid authority_state"


def test_validation_state_not_valid_fails_builder_eligibility() -> None:
    spec = _valid_specification_object()
    spec["validation_state"] = "incomplete"

    result = validate_builder_eligibility(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid validation_state"


def test_readiness_state_not_ready_for_build_fails_builder_eligibility() -> None:
    spec = _valid_specification_object()
    spec["readiness_state"] = "needs_clarification"

    result = validate_builder_eligibility(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid readiness_state"


def test_save_ready_state_not_true_fails_builder_eligibility() -> None:
    spec = _valid_specification_object()
    spec["save_ready_state"] = False

    result = validate_builder_eligibility(spec)

    assert result.failed() is True
    assert result.failure_reason == "save_ready_state must be true"


def test_clarification_required_not_false_fails_builder_eligibility() -> None:
    spec = _valid_specification_object()
    spec["clarification_required"] = True

    result = validate_builder_eligibility(spec)

    assert result.failed() is True
    assert result.failure_reason == "clarification_required must be false"


def test_missing_trace_log_fails() -> None:
    spec = _valid_specification_object()
    spec.pop("trace_log")

    result = validate_specification_object(spec)

    assert result.failed() is True


def test_invalid_trace_log_source_system_fails() -> None:
    spec = _valid_specification_object()
    spec["trace_log"]["source_system"] = "external"

    result = validate_specification_object(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid trace_log source_system"


def test_missing_lineage_fails() -> None:
    spec = _valid_specification_object()
    spec.pop("lineage")

    result = validate_specification_object(spec)

    assert result.failed() is True


def test_invalid_lineage_created_from_fails() -> None:
    spec = _valid_specification_object()
    spec["lineage"]["created_from"] = "external"

    result = validate_specification_object(spec)

    assert result.failed() is True
    assert result.failure_reason == "invalid lineage created_from"


def test_malformed_structure_fails() -> None:
    spec = _valid_specification_object()
    spec["structure"] = "not-a-dict"

    result = validate_specification_object(spec)

    assert result.failed() is True
    assert result.failure_reason == "structure must be a dictionary"


def test_missing_structure_field_fails() -> None:
    spec = _valid_specification_object()
    spec["structure"].pop("system_name")

    result = validate_specification_object(spec)

    assert result.failed() is True
    assert result.failure_reason == "structure missing required field"
    assert result.failing_field == "system_name"


def test_is_builder_eligible_returns_true_for_valid_spec() -> None:
    spec = _valid_specification_object()

    assert is_builder_eligible(spec) is True


def test_is_builder_eligible_returns_false_for_invalid_spec() -> None:
    spec = _valid_specification_object()
    spec["validation_state"] = "invalid"

    assert is_builder_eligible(spec) is False


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
