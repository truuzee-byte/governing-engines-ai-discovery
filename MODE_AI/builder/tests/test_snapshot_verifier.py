from __future__ import annotations

import copy

from builder.handoff.snapshot_verifier import verify_snapshot_continuity
from builder.handoff.specification_receiver import ReceivedSpecification, receive_specification
from specs.handoff_gate import approve_builder_handoff
from specs.spec_engine import create_specification_object
from specs.spec_snapshot import create_spec_snapshot


def test_valid_snapshot_continuity_passes() -> None:
    assert verify_snapshot_continuity(_received_specification()) is True


def test_snapshot_payload_mismatch_fails() -> None:
    received = _received_specification()
    received.snapshot["spec_payload"]["structure"]["system_name"] = "Changed"

    assert verify_snapshot_continuity(received) is False


def test_spec_id_mismatch_fails() -> None:
    received = _received_specification()
    received.snapshot["spec_id"] = "different"

    assert verify_snapshot_continuity(received) is False


def test_snapshot_hash_mismatch_fails() -> None:
    received = _received_specification()
    received.snapshot["spec_hash"] = "bad_hash"

    assert verify_snapshot_continuity(received) is False


def test_malformed_snapshot_fails() -> None:
    received = _received_specification()
    received.snapshot.clear()

    assert verify_snapshot_continuity(received) is False


def test_malformed_specification_object_fails() -> None:
    received = _received_specification()
    received.specification_object.clear()

    assert verify_snapshot_continuity(received) is False


def _received_specification() -> ReceivedSpecification:
    spec = create_specification_object(
        {
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
            "governance_constraints": ["no_raw_conversation"],
            "execution_authority": "operator_confirmed",
            "receipt_requirements": ["build_receipt"],
            "runtime_target": None,
            "source_trace_reference": "trace_source_REQ-001",
            "artifact_structure": {
                "directories": ["reports"],
                "files": ["reports/result.txt"],
            },
        }
    )
    snapshot = create_spec_snapshot(spec)
    return receive_specification(copy.deepcopy(approve_builder_handoff(spec, snapshot)))
