from __future__ import annotations

import json

import pytest

from specs.spec_engine import (
    create_lineage,
    create_specification_object,
    create_trace_log,
    generate_spec_id,
    normalize_safe_identifier,
    validate_interpreted_build_request,
)


def test_create_specification_object_emits_dict() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert isinstance(spec, dict)


def test_object_type_is_specification_object() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["object_type"] == "SpecificationObject"


def test_object_version_is_one_point_zero() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["object_version"] == "1.0"


def test_spec_id_present() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["spec_id"]


def test_spec_class_is_buildspec() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["spec_class"] == "BuildSpec"


def test_metadata_present() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert isinstance(spec["metadata"], dict)


def test_structure_present() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert isinstance(spec["structure"], dict)


def test_dependencies_present_as_list() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert isinstance(spec["dependencies"], list)


def test_authority_state_is_handoff_approved() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["authority_state"] == "handoff_approved"


def test_validation_state_is_valid() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["validation_state"] == "valid"


def test_readiness_state_is_ready_for_build() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["readiness_state"] == "ready_for_build"


def test_save_ready_state_is_true() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["save_ready_state"] is True


def test_clarification_required_is_false() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["clarification_required"] is False


def test_trace_log_present() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert isinstance(spec["trace_log"], dict)


def test_lineage_present() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert isinstance(spec["lineage"], dict)


def test_artifact_structure_present() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert isinstance(spec["artifact_structure"], dict)


def test_artifact_structure_defaults_to_empty_directories_and_files() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())

    assert spec["artifact_structure"] == {
        "directories": [],
        "files": [],
    }


def test_artifact_structure_is_preserved_if_valid_input_exists() -> None:
    request = _valid_interpreted_build_request()
    request["artifact_structure"] = {
        "directories": ["reports"],
        "files": ["reports/result.json"],
    }

    spec = create_specification_object(request)

    assert spec["artifact_structure"] == {
        "directories": ["reports"],
        "files": ["reports/result.json"],
    }


def test_raw_conversation_does_not_appear_in_output_payload() -> None:
    spec = create_specification_object(_valid_interpreted_build_request())
    serialized = json.dumps(spec)

    assert "raw conversation" not in serialized
    assert "build this from my message" not in serialized


def test_missing_required_interpreted_build_request_field_fails_validation() -> None:
    request = _valid_interpreted_build_request()
    request.pop("system_name")

    result = validate_interpreted_build_request(request)

    assert result.failed() is True
    assert result.failure_reason == "missing required interpreted_build_request field"


def test_invalid_system_name_fails_validation() -> None:
    request = _valid_interpreted_build_request()
    request["system_name"] = ""

    result = validate_interpreted_build_request(request)

    assert result.failed() is True
    assert result.failure_reason == "invalid system_name"


def test_invalid_request_id_fails_validation() -> None:
    request = _valid_interpreted_build_request()
    request["request_id"] = ""

    result = validate_interpreted_build_request(request)

    assert result.failed() is True
    assert result.failure_reason == "invalid request_id"


def test_invalid_source_trace_reference_fails_validation() -> None:
    request = _valid_interpreted_build_request()
    request["source_trace_reference"] = ""

    result = validate_interpreted_build_request(request)

    assert result.failed() is True
    assert result.failure_reason == "invalid source_trace_reference"


def test_invalid_runtime_target_type_fails_validation() -> None:
    request = _valid_interpreted_build_request()
    request["runtime_target"] = 42

    result = validate_interpreted_build_request(request)

    assert result.failed() is True
    assert result.failure_reason == "invalid interpreted_build_request field type"


def test_invalid_artifact_structure_fails_validation() -> None:
    request = _valid_interpreted_build_request()
    request["artifact_structure"] = "not-a-dict"

    result = validate_interpreted_build_request(request)

    assert result.failed() is True
    assert result.failure_reason == "invalid artifact_structure"


def test_generate_spec_id_returns_deterministic_safe_id() -> None:
    first = generate_spec_id("Diagnostic Tool", "REQ-001")
    second = generate_spec_id("Diagnostic Tool", "REQ-001")

    assert first == second
    assert first == "spec_diagnostic_tool_REQ-001"


def test_normalize_safe_identifier_removes_path_separators_and_dots() -> None:
    assert normalize_safe_identifier("Diagnostic/Tool.V1") == "diagnostic_tool_v1"


def test_create_trace_log_returns_required_shape() -> None:
    trace_log = create_trace_log(
        spec_id="spec_diagnostic_tool_REQ-001",
        source_trace_reference="trace_source_REQ-001",
    )

    assert trace_log == {
        "trace_id": "trace_spec_diagnostic_tool_REQ-001",
        "source_system": "mode_ai",
        "interpretation_trace_reference": "trace_source_REQ-001",
        "validation_trace_reference": "validation_spec_diagnostic_tool_REQ-001",
        "handoff_trace_reference": "handoff_spec_diagnostic_tool_REQ-001",
    }


def test_create_lineage_returns_required_shape() -> None:
    lineage = create_lineage(
        spec_id="spec_diagnostic_tool_REQ-001",
        source_trace_reference="trace_source_REQ-001",
    )

    assert lineage == {
        "lineage_id": "lineage_spec_diagnostic_tool_REQ-001",
        "parent_refs": [],
        "source_refs": ["trace_source_REQ-001"],
        "revision_history": [],
        "created_from": "mode_ai",
        "current_version": "1.0",
    }


def test_create_specification_object_raises_value_error_when_validation_fails() -> None:
    request = _valid_interpreted_build_request()
    request["system_name"] = ""

    with pytest.raises(ValueError):
        create_specification_object(request)


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


@pytest.mark.parametrize("authority", ["draft_only", "pending_save", "save_confirmed", "handoff_approved", "authority_granted"])
def test_explicit_canonical_authority_is_preserved(authority):
    request = _valid_interpreted_build_request()
    request["authority_state"] = authority
    assert create_specification_object(request)["authority_state"] == authority


@pytest.mark.parametrize("missing", ["authority_state", "validation_state", "readiness_state",
                                     "save_ready_state", "clarification_required", "all"])
def test_omitted_states_never_manufacture_builder_eligibility(missing):
    from specs.spec_engine import require_builder_specification
    request = _valid_interpreted_build_request()
    fields = ("authority_state", "validation_state", "readiness_state",
              "save_ready_state", "clarification_required")
    for field in fields if missing == "all" else (missing,):
        request.pop(field)
    spec = create_specification_object(request)
    with pytest.raises(ValueError, match="ineligible"):
        require_builder_specification(spec)
    if missing == "all":
        assert {field: spec[field] for field in fields} == {
            "authority_state": "draft_only", "validation_state": "incomplete",
            "readiness_state": "needs_clarification", "save_ready_state": False,
            "clarification_required": True,
        }


@pytest.mark.parametrize("field,value", [
    ("authority_state", {}), ("authority_state", []), ("authority_state", None),
    ("authority_state", True), ("authority_state", "APPROVED"),
    ("authority_state", " handoff_approved"), ("validation_state", {}),
    ("validation_state", "unknown"), ("readiness_state", "unknown"),
    ("readiness_state", {"builder_ready": True}), ("clarification_required", 0),
    ("save_ready_state", 1), ("execution_authority", "unknown"),
])
def test_factory_rejects_invalid_states_without_coercion(field, value):
    request = _valid_interpreted_build_request()
    request[field] = value
    with pytest.raises(ValueError, match=field):
        create_specification_object(request)


def test_factory_preserves_builder_fields_without_aliasing():
    request = _valid_interpreted_build_request()
    request.update({
        "artifact_structure": {"directories": [], "files": ["a.py"],
                               "approved_files": {"a.py": "pass"}, "existing_files": []},
        "execution": {"authorized_create_scope": ["a.py"], "approved_commands": []},
        "validation": {"commands": [["python", "a.py"]], "requirements": ["required_validation_must_execute"]},
        "evidence": {"requirements": ["receipt"]},
        "completion": {"requirements": ["validation_not_failed"]},
    })
    spec = create_specification_object(request)
    for field in ("artifact_structure", "execution", "validation", "evidence", "completion"):
        assert spec[field] == request[field]
    request["artifact_structure"]["approved_files"]["a.py"] = "changed"
    request["validation"]["commands"].clear()
    assert spec["artifact_structure"]["approved_files"]["a.py"] == "pass"
    assert spec["validation"]["commands"] == [["python", "a.py"]]
