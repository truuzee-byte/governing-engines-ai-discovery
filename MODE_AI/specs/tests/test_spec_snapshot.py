from __future__ import annotations

import copy

from specs.spec_engine import create_specification_object
from specs.spec_snapshot import (
    SpecSnapshot,
    canonical_serialize,
    create_spec_snapshot,
    hash_specification_object,
    snapshot_to_dict,
    verify_spec_snapshot,
)


def test_create_spec_snapshot_returns_spec_snapshot() -> None:
    spec = _valid_specification_object()

    snapshot = create_spec_snapshot(spec)

    assert isinstance(snapshot, SpecSnapshot)


def test_snapshot_contains_required_fields() -> None:
    spec = _valid_specification_object()

    snapshot = create_spec_snapshot(spec)
    payload = snapshot.to_dict()

    assert payload["snapshot_id"]
    assert payload["spec_id"] == spec["spec_id"]
    assert payload["spec_hash"]
    assert payload["snapshot_ts"]
    assert payload["spec_payload"] == spec


def test_same_specification_object_produces_same_hash() -> None:
    spec = _valid_specification_object()

    first_hash = hash_specification_object(spec)
    second_hash = hash_specification_object(copy.deepcopy(spec))

    assert first_hash == second_hash


def test_changed_specification_object_produces_different_hash() -> None:
    spec = _valid_specification_object()
    changed_spec = copy.deepcopy(spec)
    changed_spec["structure"]["system_name"] = "Changed Diagnostic Tool"

    assert hash_specification_object(spec) != hash_specification_object(changed_spec)


def test_verify_spec_snapshot_passes_valid_snapshot() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)

    result = verify_spec_snapshot(snapshot)

    assert result.passed() is True


def test_verify_spec_snapshot_fails_if_hash_mismatches() -> None:
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

    result = verify_spec_snapshot(invalid_snapshot)

    assert result.failed() is True
    assert result.failure_reason == "snapshot hash mismatch"


def test_verify_spec_snapshot_fails_if_snapshot_spec_id_mismatches_payload_spec_id() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)
    snapshot_payload = snapshot.to_dict()

    invalid_snapshot = SpecSnapshot(
        snapshot_id=snapshot_payload["snapshot_id"],
        spec_id="different_spec_id",
        spec_hash=hash_specification_object(snapshot_payload["spec_payload"]),
        snapshot_ts=snapshot_payload["snapshot_ts"],
        spec_payload=snapshot_payload["spec_payload"],
    )

    result = verify_spec_snapshot(invalid_snapshot)

    assert result.failed() is True
    assert result.failure_reason == "snapshot spec_id mismatch"


def test_snapshot_to_dict_returns_expected_shape() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)

    payload = snapshot_to_dict(snapshot)

    assert set(payload.keys()) == {
        "snapshot_id",
        "spec_id",
        "spec_hash",
        "snapshot_ts",
        "spec_payload",
    }


def test_canonical_serialize_is_deterministic_regardless_of_key_order() -> None:
    first = {
        "b": 2,
        "a": {
            "d": 4,
            "c": 3,
        },
    }
    second = {
        "a": {
            "c": 3,
            "d": 4,
        },
        "b": 2,
    }

    assert canonical_serialize(first) == canonical_serialize(second)


def test_snapshot_payload_cannot_mutate_original_specification_object_accidentally() -> None:
    spec = _valid_specification_object()
    snapshot = create_spec_snapshot(spec)

    spec["structure"]["system_name"] = "Mutated After Snapshot"

    assert snapshot.to_dict()["spec_payload"]["structure"]["system_name"] == "Diagnostic Tool"


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
    return create_specification_object(_valid_interpreted_build_request())
