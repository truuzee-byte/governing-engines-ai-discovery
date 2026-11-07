from __future__ import annotations

import pytest

from builder.handoff.specification_receiver import (
    ReceivedSpecification,
    receive_specification,
)
from specs.handoff_gate import approve_builder_handoff
from specs.spec_engine import create_specification_object
from specs.spec_snapshot import create_spec_snapshot


def test_valid_handoff_payload_accepted() -> None:
    received = receive_specification(_valid_handoff_payload())

    assert isinstance(received, ReceivedSpecification)


def test_all_fields_preserved() -> None:
    handoff = _valid_handoff_payload()
    received = receive_specification(handoff)

    assert received.specification_object == handoff["specification_object"]
    assert received.snapshot == handoff["snapshot"]
    assert received.spec_reference == handoff["spec_reference"]
    assert received.spec_hash == handoff["spec_hash"]
    assert received.builder_target == handoff["builder_target"]
    assert received.authority_state == handoff["authority_state"]
    assert received.handoff_trace_reference == handoff["handoff_trace_reference"]


def test_invalid_handoff_payload_rejected() -> None:
    with pytest.raises(ValueError, match="invalid handoff payload"):
        receive_specification("not-a-dict")


def test_missing_specification_object_rejected() -> None:
    handoff = _valid_handoff_payload()
    handoff.pop("specification_object")

    with pytest.raises(ValueError, match="missing specification_object"):
        receive_specification(handoff)


def test_missing_snapshot_rejected() -> None:
    handoff = _valid_handoff_payload()
    handoff.pop("snapshot")

    with pytest.raises(ValueError, match="missing snapshot"):
        receive_specification(handoff)


def test_missing_authority_state_rejected() -> None:
    handoff = _valid_handoff_payload()
    handoff.pop("authority_state")

    with pytest.raises(ValueError, match="missing authority_state"):
        receive_specification(handoff)


def test_handoff_not_approved_rejected() -> None:
    handoff = _valid_handoff_payload()
    handoff["handoff_status"] = "REJECTED"

    with pytest.raises(ValueError, match="handoff not approved"):
        receive_specification(handoff)


@pytest.mark.parametrize("authority", [None, {}, [], True, 1, "APPROVED", "unknown", " handoff_approved", "authority_granted"])
def test_malformed_or_conflicting_envelope_authority_rejected(authority):
    handoff = _valid_handoff_payload()
    handoff["authority_state"] = authority
    with pytest.raises(ValueError, match="authority_state"):
        receive_specification(handoff)


@pytest.mark.parametrize("field,value", [
    ("authority_state", "draft_only"), ("authority_state", {}),
    ("authority_state", "unknown"), ("validation_state", "invalid"),
    ("validation_state", {}), ("readiness_state", "needs_clarification"),
    ("readiness_state", []), ("save_ready_state", False),
    ("clarification_required", True),
])
def test_receiver_independently_rejects_ineligible_spec(field, value):
    handoff = _valid_handoff_payload()
    handoff["specification_object"][field] = value
    with pytest.raises(ValueError, match=field):
        receive_specification(handoff)


def test_receiver_rejects_missing_spec_authority():
    handoff = _valid_handoff_payload()
    del handoff["specification_object"]["authority_state"]
    with pytest.raises(ValueError, match="authority_state"):
        receive_specification(handoff)


def test_receiver_rejects_conflicting_snapshot_authority():
    handoff = _valid_handoff_payload()
    handoff["snapshot"]["spec_payload"]["authority_state"] = "authority_granted"
    with pytest.raises(ValueError, match="snapshot"):
        receive_specification(handoff)


@pytest.mark.parametrize("field", ["spec_reference", "spec_hash"])
def test_receiver_rejects_conflicting_spec_reference(field):
    handoff = _valid_handoff_payload()
    handoff[field] = "different"
    with pytest.raises(ValueError, match="mismatch"):
        receive_specification(handoff)


def _valid_handoff_payload() -> dict:
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
    return approve_builder_handoff(spec, snapshot)
