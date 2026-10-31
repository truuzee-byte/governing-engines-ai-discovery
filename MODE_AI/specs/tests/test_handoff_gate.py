from __future__ import annotations

import copy

import pytest

from specs.handoff_gate import (
    approve_builder_handoff,
    create_handoff_payload,
    validate_handoff,
)
from specs.spec_engine import create_specification_object
from specs.spec_snapshot import SpecSnapshot, create_spec_snapshot, hash_specification_object


def test_valid_buildspec_and_valid_snapshot_allows_handoff() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)

    result = validate_handoff(spec, snapshot)

    assert result.passed() is True


def test_approve_builder_handoff_returns_dict() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)

    payload = approve_builder_handoff(spec, snapshot)

    assert isinstance(payload, dict)


def test_approved_payload_contains_required_fields() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)

    payload = approve_builder_handoff(spec, snapshot)

    assert payload["handoff_status"] == "APPROVED"
    assert payload["handoff_type"] == "builder_execution"
    assert payload["specification_object"] == spec
    assert payload["snapshot"] == snapshot.to_dict()
    assert payload["spec_reference"] == spec["spec_id"]
    assert payload["spec_hash"] == snapshot.spec_hash
    assert payload["builder_target"] == spec["structure"]["system_name"]
    assert payload["authority_state"] == spec["authority_state"]
    assert payload["handoff_trace_reference"] == spec["trace_log"]["handoff_trace_reference"]


def test_validate_handoff_passes_valid_spec_and_snapshot() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)

    result = validate_handoff(spec, snapshot)

    assert result.passed() is True


def test_non_buildspec_rejects() -> None:
    spec = _valid_specification_object()
    spec["spec_class"] = "OtherSpec"
    snapshot = create_spec_snapshot(spec)

    result = validate_handoff(spec, snapshot)

    assert result.failed() is True
    assert result.failure_reason == "SpecificationObject handoff eligibility failed"


def test_invalid_authority_state_rejects() -> None:
    spec = _valid_specification_object()
    spec["authority_state"] = "draft_only"
    snapshot = create_spec_snapshot(spec)

    result = validate_handoff(spec, snapshot)

    assert result.failed() is True


def test_validation_state_not_valid_rejects() -> None:
    spec = _valid_specification_object()
    spec["validation_state"] = "invalid"
    snapshot = create_spec_snapshot(spec)

    result = validate_handoff(spec, snapshot)

    assert result.failed() is True


def test_readiness_state_not_ready_for_build_rejects() -> None:
    spec = _valid_specification_object()
    spec["readiness_state"] = "needs_clarification"
    snapshot = create_spec_snapshot(spec)

    result = validate_handoff(spec, snapshot)

    assert result.failed() is True


def test_clarification_required_true_rejects() -> None:
    spec = _valid_specification_object()
    spec["clarification_required"] = True
    snapshot = create_spec_snapshot(spec)

    result = validate_handoff(spec, snapshot)

    assert result.failed() is True


def test_missing_snapshot_rejects() -> None:
    spec = _valid_specification_object()

    result = validate_handoff(spec, None)

    assert result.failed() is True
    assert result.failure_reason == "snapshot is required"


def test_invalid_snapshot_rejects() -> None:
    spec = _valid_specification_object()

    result = validate_handoff(spec, {"invalid": "snapshot"})

    assert result.failed() is True
    assert result.failure_reason == "invalid snapshot"


def test_snapshot_spec_id_mismatch_rejects() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)
    snapshot_payload = snapshot.to_dict()

    invalid_snapshot = SpecSnapshot(
        snapshot_id=snapshot_payload["snapshot_id"],
        spec_id="different_spec_id",
        spec_hash=snapshot_payload["spec_hash"],
        snapshot_ts=snapshot_payload["snapshot_ts"],
        spec_payload=snapshot_payload["spec_payload"],
    )

    result = validate_handoff(spec, invalid_snapshot)

    assert result.failed() is True


def test_snapshot_payload_mismatch_rejects() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)
    changed_spec = copy.deepcopy(spec)
    changed_spec["structure"]["system_name"] = "Changed Diagnostic Tool"

    result = validate_handoff(changed_spec, snapshot)

    assert result.failed() is True
    assert result.failure_reason in {
        "snapshot payload mismatch",
        "snapshot hash mismatch",
    }


def test_snapshot_hash_mismatch_rejects() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)
    snapshot_payload = snapshot.to_dict()

    invalid_snapshot = SpecSnapshot(
        snapshot_id=snapshot_payload["snapshot_id"],
        spec_id=snapshot_payload["spec_id"],
        spec_hash="bad_hash",
        snapshot_ts=snapshot_payload["snapshot_ts"],
        spec_payload=snapshot_payload["spec_payload"],
    )

    result = validate_handoff(spec, invalid_snapshot)

    assert result.failed() is True


def test_missing_handoff_trace_reference_rejects() -> None:
    spec = _valid_specification_object()
    spec["trace_log"]["handoff_trace_reference"] = ""
    snapshot = create_spec_snapshot(spec)

    result = validate_handoff(spec, snapshot)

    assert result.failed() is True


def test_approve_builder_handoff_raises_value_error_on_rejection() -> None:
    spec = _valid_specification_object()
    spec["validation_state"] = "invalid"
    snapshot = create_spec_snapshot(spec)

    with pytest.raises(ValueError):
        approve_builder_handoff(spec, snapshot)


def test_dict_snapshot_fixture_is_accepted_if_valid() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec).to_dict()

    result = validate_handoff(spec, snapshot)

    assert result.passed() is True


def test_no_partial_handoff_payload_is_returned_on_failure() -> None:
    spec = _valid_specification_object()
    spec["validation_state"] = "invalid"
    snapshot = create_spec_snapshot(spec)

    with pytest.raises(ValueError):
        create_handoff_payload(spec, snapshot)


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
